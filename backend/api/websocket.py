"""WebSocket 网关模块。

负责会话管理、任务观察、用户中断和流式状态推送。
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.api.protocol import MessageFactory, MessageType, UserMessage
from backend.core.workflow import AgentWorkflow

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._session_data: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """接受 WebSocket 连接。"""
        await websocket.accept()
        self._active_connections[session_id] = websocket
        self._session_data[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "message_count": 0,
        }
        logger.info("WebSocket 连接建立: %s", session_id)

    def disconnect(self, session_id: str) -> None:
        """断开 WebSocket 连接。"""
        self._active_connections.pop(session_id, None)
        self._session_data.pop(session_id, None)
        logger.info("WebSocket 连接断开: %s", session_id)

    async def send_message(self, session_id: str, message: BaseModel) -> None:
        """发送消息。"""
        websocket = self._active_connections.get(session_id)
        if websocket is None:
            return
        await websocket.send_text(message.model_dump_json())
        if session_id in self._session_data:
            self._session_data[session_id]["message_count"] += 1

    async def broadcast(self, message: BaseModel) -> None:
        """广播消息到所有连接。"""
        for session_id in list(self._active_connections):
            await self.send_message(session_id, message)

    def is_connected(self, session_id: str) -> bool:
        """检查连接是否存在。"""
        return session_id in self._active_connections

    def get_session_ids(self) -> list[str]:
        """获取所有活跃会话 ID。"""
        return list(self._active_connections.keys())

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """获取会话连接信息。"""
        return self._session_data.get(session_id)


manager = ConnectionManager()


class SessionContext:
    """会话上下文。"""

    def __init__(self, session_id: str, user_id: str = "default") -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.workflow: AgentWorkflow | None = None
        self.current_task: asyncio.Task[None] | None = None
        self.status = "idle"
        self.last_error: str | None = None
        self.events: list[dict[str, Any]] = []
        self._interrupted = False

    def interrupt(self) -> None:
        """中断当前执行。"""
        self._interrupted = True
        self.status = "interrupted"
        self.record_event("status", "用户中断", "已请求中断当前执行")
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def is_interrupted(self) -> bool:
        """检查是否被中断。"""
        return self._interrupted

    def reset(self) -> None:
        """重置中断状态。"""
        self._interrupted = False
        self.status = "idle"
        self.last_error = None

    def start_task(self, task: asyncio.Task[None]) -> None:
        """记录当前后台任务。"""
        self.current_task = task
        self.status = "processing"
        self.last_error = None

    def finish_task(self, status: str) -> None:
        """标记任务结束。"""
        self.status = status
        self.current_task = None

    def record_event(
        self,
        event_type: str,
        title: str,
        message: str = "",
        *,
        progress: int | None = None,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录供前端观察的任务事件。"""
        self.events.append({
            "id": f"{self.session_id}-{len(self.events) + 1}",
            "type": event_type,
            "title": title,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "progress": progress,
            "stage": stage,
            "details": details or {},
        })
        self.events = self.events[-200:]

    def snapshot(self) -> dict[str, Any]:
        """返回会话快照。"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "interrupted": self._interrupted,
            "running": self.current_task is not None and not self.current_task.done(),
            "last_error": self.last_error,
            "events": self.events,
            "connection": manager.get_session_info(self.session_id),
        }


sessions: dict[str, SessionContext] = {}


def get_or_create_session(session_id: str, user_id: str = "default") -> SessionContext:
    """获取或创建会话。"""
    if session_id not in sessions:
        sessions[session_id] = SessionContext(session_id, user_id)
    return sessions[session_id]


async def process_user_message(
    session_id: str,
    user_message: UserMessage,
) -> AsyncGenerator[BaseModel, None]:
    """处理用户消息并生成响应流。"""
    context = get_or_create_session(session_id, user_message.user_id)
    context.status = "processing"
    context.record_event("status", "开始处理", "已接收用户请求")

    yield MessageFactory.create_status(
        session_id=session_id,
        status="processing",
        message="开始处理请求...",
    )

    try:
        if context.workflow is None:
            context.workflow = AgentWorkflow(
                user_id=user_message.user_id,
                cancellation_checker=context.is_interrupted,
            )
            context.workflow.compile()
        else:
            context.workflow.set_cancellation_checker(context.is_interrupted)

        yield MessageFactory.create_progress(
            session_id=session_id,
            stage="intent",
            progress=10,
            message="正在识别意图...",
            details={"observable": True},
        )

        result = await context.workflow.run(
            user_query=user_message.content,
            thread_id=session_id,
            user_context=user_message.context,
        )

        if context.is_interrupted():
            yield MessageFactory.create_status(
                session_id=session_id,
                status="interrupted",
                message="执行已被用户中断",
            )
            return

        yield MessageFactory.create_progress(
            session_id=session_id,
            stage="completed",
            progress=100,
            message="处理完成",
        )

        final_result = str(result.get("final_result") or "")
        if not final_result:
            execution_results = result.get("execution_results", [])
            if execution_results:
                final_result = "\n".join(
                    f"- {step.get('action', '')}: {step.get('result', '')}"
                    for step in execution_results
                )
            else:
                final_result = "处理完成，但未生成结果"

        plan_data = result.get("plan")
        plan_dict = dict(plan_data) if plan_data else None

        yield MessageFactory.create_agent_message(
            session_id=session_id,
            content=final_result,
            intent=str(result.get("intent", "")),
            plan=plan_dict,
        )

        yield MessageFactory.create_status(
            session_id=session_id,
            status="completed",
            message="处理完成",
        )
    except asyncio.CancelledError:
        yield MessageFactory.create_status(
            session_id=session_id,
            status="interrupted",
            message="执行已被用户中断",
        )
    except Exception as exc:
        context.last_error = str(exc)
        logger.exception("处理消息时发生错误: %s", exc)
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="PROCESSING_ERROR",
            error_message=str(exc),
        )


async def stream_workflow_events(
    session_id: str,
    workflow: AgentWorkflow,
    user_query: str,
) -> AsyncGenerator[BaseModel, None]:
    """流式输出 LangGraph 工作流事件。"""
    context = sessions.get(session_id)
    if not context:
        return

    try:
        if workflow._compiled_workflow is None:
            workflow.compile()

        from backend.core.state import create_initial_state

        initial_state = create_initial_state(user_query)
        config = {"configurable": {"thread_id": session_id}}

        assert workflow._compiled_workflow is not None
        async for event in workflow._compiled_workflow.astream_events(
            initial_state,
            config,
            version="v1",
        ):
            if context.is_interrupted():
                yield MessageFactory.create_status(
                    session_id=session_id,
                    status="interrupted",
                    message="执行已被用户中断",
                )
                break

            event_type = event.get("event", "")
            name = event.get("name", "")
            data = event.get("data", {})

            if event_type == "on_chain_start":
                yield MessageFactory.create_progress(
                    session_id=session_id,
                    stage=name,
                    progress=0,
                    message=f"开始执行: {name}",
                )
            elif event_type == "on_chain_end":
                yield MessageFactory.create_progress(
                    session_id=session_id,
                    stage=name,
                    progress=100,
                    message=f"完成: {name}",
                )
            elif event_type == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content"):
                    yield MessageFactory.create_agent_message(
                        session_id=session_id,
                        content=str(chunk.content),
                        is_streaming=True,
                    )
    except Exception as exc:
        logger.exception("流式输出错误: %s", exc)
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="STREAM_ERROR",
            error_message=str(exc),
        )


async def _send_and_record(session_id: str, message: BaseModel) -> None:
    """发送消息并写入会话事件。"""
    context = sessions.get(session_id)
    if context is not None:
        data = message.model_dump()
        message_type = data.get("type", "")
        if message_type == MessageType.PROGRESS:
            context.record_event(
                "progress",
                str(data.get("stage") or "进度"),
                str(data.get("message") or ""),
                progress=int(data.get("progress") or 0),
                stage=str(data.get("stage") or ""),
                details=dict(data.get("details") or {}),
            )
        elif message_type == MessageType.STATUS:
            status = str(data.get("status") or "")
            context.status = status
            context.record_event("status", status, str(data.get("message") or ""))
        elif message_type == MessageType.ERROR:
            context.last_error = str(data.get("error_message") or "")
            context.status = "error"
            context.record_event("error", str(data.get("error_code") or "错误"), context.last_error)
        elif message_type == MessageType.AGENT:
            context.record_event("agent", "Agent 输出", str(data.get("content") or "")[:500])

    await manager.send_message(session_id, message)


async def _run_user_message(session_id: str, user_message: UserMessage) -> None:
    """后台执行用户请求，避免阻塞 WebSocket 接收循环。"""
    context = get_or_create_session(session_id, user_message.user_id)
    final_status = "completed"
    try:
        async for response in process_user_message(session_id, user_message):
            if not manager.is_connected(session_id):
                break
            await _send_and_record(session_id, response)
            if getattr(response, "type", None) == MessageType.STATUS:
                status = getattr(response, "status", "")
                if status in {"completed", "interrupted", "error"}:
                    final_status = str(status)
    except asyncio.CancelledError:
        final_status = "interrupted"
        await _send_and_record(
            session_id,
            MessageFactory.create_status(
                session_id=session_id,
                status="interrupted",
                message="执行已被用户中断",
            ),
        )
    except Exception as exc:
        final_status = "error"
        context.last_error = str(exc)
        logger.exception("后台任务错误: %s", exc)
        await _send_and_record(
            session_id,
            MessageFactory.create_error(
                session_id=session_id,
                error_code="PROCESSING_ERROR",
                error_message=str(exc),
            ),
        )
    finally:
        context.finish_task(final_status)


@router.get("/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, Any]:
    """获取会话状态和事件快照。"""
    context = get_or_create_session(session_id)
    return context.snapshot()


@router.websocket("/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str = "default",
) -> None:
    """WebSocket 端点。"""
    await manager.connect(websocket, session_id)
    context = get_or_create_session(session_id, user_id)

    try:
        await _send_and_record(
            session_id,
            MessageFactory.create_status(
                session_id=session_id,
                status="connected",
                message="WebSocket 连接成功",
            ),
        )

        while True:
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "")

                if message_type == MessageType.USER:
                    if context.current_task and not context.current_task.done():
                        await _send_and_record(
                            session_id,
                            MessageFactory.create_error(
                                session_id=session_id,
                                error_code="TASK_RUNNING",
                                error_message="当前已有任务在执行，请先中断或等待完成",
                            ),
                        )
                        continue

                    user_message = UserMessage(**message_data)
                    context.reset()
                    task = asyncio.create_task(_run_user_message(session_id, user_message))
                    context.start_task(task)

                elif message_type == MessageType.INTERRUPT:
                    context.interrupt()
                    await _send_and_record(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="interrupted",
                            message="已中断当前执行",
                        ),
                    )

                elif message_type == "ping":
                    await _send_and_record(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="pong",
                            message="心跳响应",
                        ),
                    )

                else:
                    await _send_and_record(
                        session_id,
                        MessageFactory.create_error(
                            session_id=session_id,
                            error_code="UNKNOWN_MESSAGE_TYPE",
                            error_message=f"未知的消息类型: {message_type}",
                        ),
                    )

            except json.JSONDecodeError:
                await _send_and_record(
                    session_id,
                    MessageFactory.create_error(
                        session_id=session_id,
                        error_code="INVALID_JSON",
                        error_message="无效的 JSON 格式",
                    ),
                )

            except Exception as exc:
                logger.exception("处理消息错误: %s", exc)
                await _send_and_record(
                    session_id,
                    MessageFactory.create_error(
                        session_id=session_id,
                        error_code="PROCESSING_ERROR",
                        error_message=str(exc),
                    ),
                )

    except WebSocketDisconnect:
        context.interrupt()
        manager.disconnect(session_id)
        sessions.pop(session_id, None)
    except Exception as exc:
        logger.exception("WebSocket 错误: %s", exc)
        context.interrupt()
        manager.disconnect(session_id)
        sessions.pop(session_id, None)


def reset_sessions() -> None:
    """重置所有会话（用于测试）。"""
    for context in sessions.values():
        context.interrupt()
    sessions.clear()
