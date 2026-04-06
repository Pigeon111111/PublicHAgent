"""WebSocket 网关模块

实现 WebSocket 连接管理、会话管理和流式输出。
"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.api.protocol import (
    MessageFactory,
    MessageType,
    UserMessage,
)
from backend.core.workflow import AgentWorkflow

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._session_data: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """接受 WebSocket 连接"""
        await websocket.accept()
        self._active_connections[session_id] = websocket
        self._session_data[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "message_count": 0,
        }
        logger.info(f"WebSocket 连接建立: {session_id}")

    def disconnect(self, session_id: str) -> None:
        """断开 WebSocket 连接"""
        self._active_connections.pop(session_id, None)
        self._session_data.pop(session_id, None)
        logger.info(f"WebSocket 连接断开: {session_id}")

    async def send_message(self, session_id: str, message: BaseModel) -> None:
        """发送消息"""
        if session_id in self._active_connections:
            websocket = self._active_connections[session_id]
            await websocket.send_text(message.model_dump_json())
            self._session_data[session_id]["message_count"] += 1

    async def broadcast(self, message: BaseModel) -> None:
        """广播消息到所有连接"""
        for session_id in self._active_connections:
            await self.send_message(session_id, message)

    def is_connected(self, session_id: str) -> bool:
        """检查连接是否存在"""
        return session_id in self._active_connections

    def get_session_ids(self) -> list[str]:
        """获取所有活跃会话 ID"""
        return list(self._active_connections.keys())

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        """获取会话信息"""
        return self._session_data.get(session_id)


manager = ConnectionManager()


class SessionContext:
    """会话上下文"""

    def __init__(self, session_id: str, user_id: str = "default") -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.workflow: AgentWorkflow | None = None
        self._interrupted = False

    def interrupt(self) -> None:
        """中断当前执行"""
        self._interrupted = True

    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self._interrupted

    def reset(self) -> None:
        """重置中断状态"""
        self._interrupted = False


sessions: dict[str, SessionContext] = {}


def get_or_create_session(session_id: str, user_id: str = "default") -> SessionContext:
    """获取或创建会话"""
    if session_id not in sessions:
        sessions[session_id] = SessionContext(session_id, user_id)
    return sessions[session_id]


async def process_user_message(
    session_id: str,
    user_message: UserMessage,
) -> AsyncGenerator[BaseModel, None]:
    """处理用户消息并生成响应流

    Args:
        session_id: 会话 ID
        user_message: 用户消息

    Yields:
        响应消息
    """
    context = get_or_create_session(session_id, user_message.user_id)

    yield MessageFactory.create_status(
        session_id=session_id,
        status="processing",
        message="开始处理请求...",
    )

    try:
        if context.workflow is None:
            context.workflow = AgentWorkflow()
            context.workflow.compile()

        yield MessageFactory.create_progress(
            session_id=session_id,
            stage="intent",
            progress=10,
            message="正在识别意图...",
        )

        result = await context.workflow.run(
            user_query=user_message.content,
            thread_id=session_id,
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

        final_result = result.get("final_result", "")
        if not final_result:
            execution_results = result.get("execution_results", [])
            if execution_results:
                final_result = "\n".join([
                    f"- {step.get('action', '')}: {step.get('result', '')}"
                    for step in execution_results
                ])
            else:
                final_result = "处理完成，但未生成结果"

        plan_data = result.get("plan")
        plan_dict = dict(plan_data) if plan_data else None

        yield MessageFactory.create_agent_message(
            session_id=session_id,
            content=final_result,
            intent=result.get("intent", ""),
            plan=plan_dict,
        )

        yield MessageFactory.create_status(
            session_id=session_id,
            status="completed",
            message="处理完成",
        )

    except Exception as e:
        logger.exception(f"处理消息时发生错误: {e}")
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="PROCESSING_ERROR",
            error_message=str(e),
        )


async def stream_workflow_events(
    session_id: str,
    workflow: AgentWorkflow,
    user_query: str,
) -> AsyncGenerator[BaseModel, None]:
    """流式输出工作流事件

    Args:
        session_id: 会话 ID
        workflow: 工作流实例
        user_query: 用户查询

    Yields:
        事件消息
    """
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
                        content=chunk.content,
                        is_streaming=True,
                    )

    except Exception as e:
        logger.exception(f"流式输出错误: {e}")
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="STREAM_ERROR",
            error_message=str(e),
        )


@router.websocket("/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str = "default",
) -> None:
    """WebSocket 端点

    Args:
        websocket: WebSocket 连接
        session_id: 会话 ID
        user_id: 用户 ID
    """
    await manager.connect(websocket, session_id)
    context = get_or_create_session(session_id, user_id)

    try:
        await manager.send_message(
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
                    user_message = UserMessage(**message_data)
                    context.reset()

                    async for response in process_user_message(session_id, user_message):
                        if not manager.is_connected(session_id):
                            break
                        await manager.send_message(session_id, response)

                elif message_type == MessageType.INTERRUPT:
                    context.interrupt()
                    await manager.send_message(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="interrupted",
                            message="已中断当前执行",
                        ),
                    )

                elif message_type == "ping":
                    await manager.send_message(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="pong",
                            message="心跳响应",
                        ),
                    )

                else:
                    await manager.send_message(
                        session_id,
                        MessageFactory.create_error(
                            session_id=session_id,
                            error_code="UNKNOWN_MESSAGE_TYPE",
                            error_message=f"未知的消息类型: {message_type}",
                        ),
                    )

            except json.JSONDecodeError:
                await manager.send_message(
                    session_id,
                    MessageFactory.create_error(
                        session_id=session_id,
                        error_code="INVALID_JSON",
                        error_message="无效的 JSON 格式",
                    ),
                )

            except Exception as e:
                logger.exception(f"处理消息错误: {e}")
                await manager.send_message(
                    session_id,
                    MessageFactory.create_error(
                        session_id=session_id,
                        error_code="PROCESSING_ERROR",
                        error_message=str(e),
                    ),
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        if session_id in sessions:
            del sessions[session_id]

    except Exception as e:
        logger.exception(f"WebSocket 错误: {e}")
        manager.disconnect(session_id)
        if session_id in sessions:
            del sessions[session_id]


def reset_sessions() -> None:
    """重置所有会话（用于测试）"""
    global sessions
    sessions = {}
