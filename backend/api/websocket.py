"""WebSocket 网关模块。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Mapping
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.api.protocol import MessageFactory, MessageType, UserMessage
from backend.core.workflow import AgentWorkflow
from backend.storage.history_storage import get_history_storage

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._session_data: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self._active_connections[session_id] = websocket
        self._session_data[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "message_count": 0,
        }
        logger.info("WebSocket 连接建立: %s", session_id)

    def disconnect(self, session_id: str) -> None:
        self._active_connections.pop(session_id, None)
        self._session_data.pop(session_id, None)
        logger.info("WebSocket 连接断开: %s", session_id)

    async def send_message(self, session_id: str, message: BaseModel) -> None:
        websocket = self._active_connections.get(session_id)
        if websocket is None:
            return
        await websocket.send_text(message.model_dump_json())
        if session_id in self._session_data:
            self._session_data[session_id]["message_count"] += 1

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._active_connections

    def get_session_ids(self) -> list[str]:
        return list(self._active_connections.keys())

    def get_session_info(self, session_id: str) -> dict[str, Any] | None:
        return self._session_data.get(session_id)


manager = ConnectionManager()


class SessionContext:
    """单会话上下文。"""

    def __init__(self, session_id: str, user_id: str = "default") -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.workflow: AgentWorkflow | None = None
        self.current_task: asyncio.Task[None] | None = None
        self.conversation_id: str | None = None
        self.current_analysis_id: str | None = None
        self.status = "idle"
        self.last_error: str | None = None
        self.events: list[dict[str, Any]] = []
        self._interrupted = False

    def interrupt(self) -> None:
        self._interrupted = True
        self.status = "interrupted"
        self.record_event("status", "用户中断", "已请求停止当前执行")
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def is_interrupted(self) -> bool:
        return self._interrupted

    def reset(self, *, clear_analysis_id: bool = True) -> None:
        self._interrupted = False
        self.status = "idle"
        self.last_error = None
        if clear_analysis_id:
            self.current_analysis_id = None

    def start_task(self, task: asyncio.Task[None]) -> None:
        self.current_task = task
        self.status = "processing"
        self.last_error = None

    def finish_task(self, status: str) -> None:
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
        self.events.append(
            {
                "id": f"{self.session_id}-{len(self.events) + 1}",
                "type": event_type,
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "progress": progress,
                "stage": stage,
                "details": details or {},
            }
        )
        self.events = self.events[-200:]

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "interrupted": self._interrupted,
            "running": self.current_task is not None and not self.current_task.done(),
            "last_error": self.last_error,
            "conversation_id": self.conversation_id,
            "current_analysis_id": self.current_analysis_id,
            "events": self.events,
            "connection": manager.get_session_info(self.session_id),
        }


sessions: dict[str, SessionContext] = {}


def get_or_create_session(session_id: str, user_id: str = "default") -> SessionContext:
    if session_id not in sessions:
        sessions[session_id] = SessionContext(session_id, user_id)
    else:
        sessions[session_id].user_id = user_id
    return sessions[session_id]


def _derive_conversation_title(content: str) -> str:
    normalized = " ".join(content.split())
    return normalized[:40] if normalized else "新对话"


def _ensure_history_conversation(context: SessionContext, user_message: UserMessage) -> str:
    storage = get_history_storage()
    conversation = storage.get_or_create_session_conversation(
        session_id=context.session_id,
        user_id=user_message.user_id,
        title=_derive_conversation_title(user_message.content),
    )
    context.conversation_id = str(conversation["id"])
    return context.conversation_id


def _append_history_message(
    context: SessionContext,
    role: str,
    content: str,
    *,
    timestamp: str | None = None,
) -> None:
    if not context.conversation_id:
        return
    storage = get_history_storage()
    try:
        storage.add_message(
            conversation_id=context.conversation_id,
            role=role,
            content=content,
            timestamp=timestamp,
        )
    except KeyError:
        return


def _hydrate_history_context(context: SessionContext, user_id: str | None = None) -> None:
    effective_user_id = user_id or context.user_id
    storage = get_history_storage()
    if context.conversation_id is None:
        conversation = storage.get_session_conversation(
            session_id=context.session_id,
            user_id=effective_user_id,
        )
        if conversation is not None:
            context.conversation_id = str(conversation["id"])
    if context.current_analysis_id is None:
        record = storage.get_latest_analysis_record_for_session(
            session_id=context.session_id,
            user_id=effective_user_id,
        )
        if record is not None:
            context.current_analysis_id = str(record["id"])


def _create_analysis_record(context: SessionContext, user_message: UserMessage) -> None:
    storage = get_history_storage()
    record = storage.create_analysis_record(
        query=user_message.content,
        intent="",
        status="processing",
        result_summary="",
        steps_count=0,
        user_id=user_message.user_id,
        session_id=context.session_id,
        conversation_id=context.conversation_id,
    )
    context.current_analysis_id = str(record["id"])


def _update_analysis_record(
    context: SessionContext,
    *,
    intent: str = "",
    status: str,
    result_summary: str = "",
    steps_count: int = 0,
    trajectory_id: str | None = None,
    evaluation_id: str | None = None,
    task_family: str = "",
    evaluation_score: float = 0.0,
    evaluation_passed: bool = False,
    evaluation_summary: str = "",
    review_status: str = "unreviewed",
) -> None:
    if not context.current_analysis_id:
        return
    storage = get_history_storage()
    storage.update_analysis_record(
        context.current_analysis_id,
        intent=intent,
        status=status,
        result_summary=result_summary[:4000],
        steps_count=steps_count,
        trajectory_id=trajectory_id,
        evaluation_id=evaluation_id,
        task_family=task_family,
        evaluation_score=evaluation_score,
        evaluation_passed=evaluation_passed,
        evaluation_summary=evaluation_summary[:1000],
        review_status=review_status,
        conversation_id=context.conversation_id,
        session_id=context.session_id,
    )


async def _ensure_workflow(context: SessionContext, user_id: str) -> AgentWorkflow:
    context.user_id = user_id
    if context.workflow is None:
        context.workflow = AgentWorkflow(
            user_id=user_id,
            cancellation_checker=context.is_interrupted,
        )
    else:
        context.workflow.set_cancellation_checker(context.is_interrupted)
    await context.workflow.ensure_compiled()
    return context.workflow


def _extract_evaluation_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    report = result.get("evaluation_report") or {}
    if not isinstance(report, Mapping):
        return {}
    return {
        "task_family": str(result.get("task_family") or report.get("task_family") or ""),
        "passed": bool(report.get("passed", False)),
        "final_score": float(result.get("evaluation_score") or report.get("final_score") or 0.0),
        "summary": str(report.get("summary") or ""),
        "hard_failures": list(report.get("hard_failures") or []),
        "score_breakdown": dict(report.get("score_breakdown") or {}),
    }


def _extract_final_result(result: Mapping[str, Any]) -> str:
    final_result = str(result.get("final_result") or "")
    if final_result:
        return final_result

    execution_results = result.get("execution_results", [])
    if execution_results:
        return "\n".join(
            f"- {step.get('action', '')}: {step.get('result', '')}"
            for step in execution_results
        )
    return "处理完成，但未生成结果。"


def _ensure_resume_history(context: SessionContext, *, user_id: str, query: str) -> None:
    storage = get_history_storage()
    if context.conversation_id is None:
        conversation = storage.get_or_create_session_conversation(
            session_id=context.session_id,
            user_id=user_id,
            title=_derive_conversation_title(query),
        )
        context.conversation_id = str(conversation["id"])
    if context.current_analysis_id is None:
        record = storage.create_analysis_record(
            query=query,
            intent="",
            status="processing",
            result_summary="恢复执行中",
            steps_count=0,
            user_id=user_id,
            session_id=context.session_id,
            conversation_id=context.conversation_id,
        )
        context.current_analysis_id = str(record["id"])


async def _build_checkpoint_status(context: SessionContext) -> dict[str, Any]:
    workflow = await _ensure_workflow(context, context.user_id)
    return await workflow.get_checkpoint_status(context.session_id)


def _persist_evaluation_and_history(
    context: SessionContext,
    result: Mapping[str, Any],
    final_result: str,
) -> dict[str, Any]:
    storage = get_history_storage()
    evaluation_report = dict(result.get("evaluation_report") or {})
    evaluation_payload: dict[str, Any] | None = None

    if context.current_analysis_id and evaluation_report:
        associated_skill = str(
            result.get("learned_skill")
            or result.get("selected_skill")
            or ""
        )
        evaluation_payload = storage.upsert_evaluation_report(
            analysis_record_id=context.current_analysis_id,
            session_id=context.session_id,
            trajectory_id=str(result.get("trajectory_id") or ""),
            task_family=str(result.get("task_family") or evaluation_report.get("task_family") or ""),
            final_score=float(result.get("evaluation_score") or evaluation_report.get("final_score") or 0.0),
            passed=bool(evaluation_report.get("passed", False)),
            summary=str(evaluation_report.get("summary") or ""),
            report_json=evaluation_report,
            associated_skill=associated_skill,
        )
        _update_analysis_record(
            context,
            intent=str(result.get("intent", "")),
            status="completed",
            result_summary=final_result,
            steps_count=len(result.get("execution_results", [])),
            trajectory_id=str(result.get("trajectory_id") or ""),
            evaluation_id=str(evaluation_payload["id"]),
            task_family=str(evaluation_payload["task_family"]),
            evaluation_score=float(evaluation_payload["final_score"]),
            evaluation_passed=bool(evaluation_payload["passed"]),
            evaluation_summary=str(evaluation_payload["summary"]),
            review_status=str(evaluation_payload["review_status"]),
        )
    else:
        _update_analysis_record(
            context,
            intent=str(result.get("intent", "")),
            status="completed",
            result_summary=final_result,
            steps_count=len(result.get("execution_results", [])),
            trajectory_id=str(result.get("trajectory_id") or ""),
        )

    _append_history_message(context, "assistant", final_result)
    return evaluation_payload or {}


async def _emit_completed_messages(
    context: SessionContext,
    *,
    session_id: str,
    result: Mapping[str, Any],
) -> AsyncGenerator[BaseModel, None]:
    yield MessageFactory.create_progress(
        session_id=session_id,
        stage="completed",
        progress=100,
        message="处理完成",
    )

    final_result = _extract_final_result(result)
    persisted_evaluation = _persist_evaluation_and_history(context, result, final_result)
    evaluation_summary = _extract_evaluation_summary(result)
    if persisted_evaluation:
        evaluation_summary["id"] = persisted_evaluation.get("id", "")
        evaluation_summary["review_status"] = persisted_evaluation.get("review_status", "unreviewed")

    plan_data = result.get("plan")
    plan_dict = dict(plan_data) if plan_data else None
    yield MessageFactory.create_agent_message(
        session_id=session_id,
        content=final_result,
        intent=str(result.get("intent", "")),
        plan=plan_dict,
        evaluation_report=evaluation_summary,
        task_family=str(result.get("task_family") or evaluation_summary.get("task_family") or ""),
        evaluation_score=float(result.get("evaluation_score") or evaluation_summary.get("final_score") or 0.0),
        analysis_id=context.current_analysis_id or "",
        trajectory_id=str(result.get("trajectory_id") or ""),
    )
    yield MessageFactory.create_status(
        session_id=session_id,
        status="completed",
        message="处理完成",
    )


async def process_user_message(
    session_id: str,
    user_message: UserMessage,
) -> AsyncGenerator[BaseModel, None]:
    context = get_or_create_session(session_id, user_message.user_id)
    _hydrate_history_context(context, user_message.user_id)
    _ensure_history_conversation(context, user_message)
    _append_history_message(context, "user", user_message.content, timestamp=user_message.timestamp)
    _create_analysis_record(context, user_message)
    context.status = "processing"
    context.record_event("status", "开始处理", "已接收用户请求")

    yield MessageFactory.create_status(
        session_id=session_id,
        status="processing",
        message="开始处理请求...",
    )

    try:
        workflow = await _ensure_workflow(context, user_message.user_id)
        yield MessageFactory.create_progress(
            session_id=session_id,
            stage="intent",
            progress=10,
            message="正在识别意图...",
            details={"observable": True},
        )
        result = await workflow.run(
            user_query=user_message.content,
            thread_id=session_id,
            user_context=user_message.context,
        )

        if context.is_interrupted():
            interrupted_message = "执行已被用户中断"
            _append_history_message(context, "system", interrupted_message)
            _update_analysis_record(
                context,
                intent=str(result.get("intent", "")),
                status="interrupted",
                result_summary=interrupted_message,
                steps_count=len(result.get("execution_results", [])),
                trajectory_id=str(result.get("trajectory_id") or ""),
            )
            yield MessageFactory.create_status(
                session_id=session_id,
                status="interrupted",
                message=interrupted_message,
            )
            return

        async for message in _emit_completed_messages(context, session_id=session_id, result=result):
            yield message
    except asyncio.CancelledError:
        interrupted_message = "执行已被用户中断"
        _append_history_message(context, "system", interrupted_message)
        _update_analysis_record(context, status="interrupted", result_summary=interrupted_message)
        yield MessageFactory.create_status(
            session_id=session_id,
            status="interrupted",
            message=interrupted_message,
        )
    except Exception as exc:  # noqa: BLE001
        context.last_error = str(exc)
        logger.exception("处理消息时发生错误: %s", exc)
        _append_history_message(context, "system", f"错误: {exc}")
        _update_analysis_record(context, status="error", result_summary=str(exc))
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="PROCESSING_ERROR",
            error_message=str(exc),
        )


async def process_resume_request(
    session_id: str,
    *,
    user_id: str = "default",
) -> AsyncGenerator[BaseModel, None]:
    context = get_or_create_session(session_id, user_id)
    _hydrate_history_context(context, user_id)

    try:
        workflow = await _ensure_workflow(context, user_id)
        checkpoint_status = await workflow.get_checkpoint_status(session_id)
        if not checkpoint_status.get("resumable"):
            yield MessageFactory.create_error(
                session_id=session_id,
                error_code="NO_RESUMABLE_CHECKPOINT",
                error_message="当前会话没有可恢复的执行状态",
                details={"checkpoint": checkpoint_status},
            )
            return

        snapshot = await workflow.get_state_snapshot(session_id)
        state_values = dict(snapshot.values or {}) if snapshot is not None else {}
        user_query = str(state_values.get("user_query") or "恢复上次任务")
        _ensure_resume_history(context, user_id=user_id, query=user_query)
        _update_analysis_record(
            context,
            intent=str(state_values.get("intent", "")),
            status="processing",
            result_summary="恢复执行中",
            steps_count=len(state_values.get("execution_results", [])),
        )
        context.status = "processing"
        context.record_event(
            "status",
            "恢复执行",
            f"将从节点 {', '.join(checkpoint_status.get('next_nodes', [])) or '未知位置'} 继续",
        )

        yield MessageFactory.create_status(
            session_id=session_id,
            status="processing",
            message="正在从持久化 checkpoint 恢复执行...",
        )
        yield MessageFactory.create_progress(
            session_id=session_id,
            stage="resume",
            progress=20,
            message="已恢复线程状态，准备继续执行",
            details={"checkpoint": checkpoint_status},
        )

        result = await workflow.resume(thread_id=session_id)
        if context.is_interrupted():
            interrupted_message = "恢复执行过程中已被用户中断"
            _append_history_message(context, "system", interrupted_message)
            _update_analysis_record(
                context,
                intent=str(result.get("intent", "")),
                status="interrupted",
                result_summary=interrupted_message,
                steps_count=len(result.get("execution_results", [])),
                trajectory_id=str(result.get("trajectory_id") or ""),
            )
            yield MessageFactory.create_status(
                session_id=session_id,
                status="interrupted",
                message=interrupted_message,
            )
            return

        async for message in _emit_completed_messages(context, session_id=session_id, result=result):
            yield message
    except asyncio.CancelledError:
        interrupted_message = "恢复执行已被用户中断"
        _append_history_message(context, "system", interrupted_message)
        _update_analysis_record(context, status="interrupted", result_summary=interrupted_message)
        yield MessageFactory.create_status(
            session_id=session_id,
            status="interrupted",
            message=interrupted_message,
        )
    except Exception as exc:  # noqa: BLE001
        context.last_error = str(exc)
        logger.exception("恢复执行时发生错误: %s", exc)
        yield MessageFactory.create_error(
            session_id=session_id,
            error_code="RESUME_ERROR",
            error_message=str(exc),
        )


async def _send_and_record(session_id: str, message: BaseModel) -> None:
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
            context.status = str(data.get("status") or "")
            context.record_event("status", context.status, str(data.get("message") or ""))
        elif message_type == MessageType.ERROR:
            context.last_error = str(data.get("error_message") or "")
            context.status = "error"
            context.record_event("error", str(data.get("error_code") or "错误"), context.last_error)
        elif message_type == MessageType.AGENT:
            context.record_event(
                "agent",
                "Agent 输出",
                str(data.get("content") or "")[:500],
                details={
                    "analysis_id": data.get("analysis_id", ""),
                    "evaluation_report": data.get("evaluation_report", {}),
                },
            )

    await manager.send_message(session_id, message)


async def _run_user_message(session_id: str, user_message: UserMessage) -> None:
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
    except Exception as exc:  # noqa: BLE001
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


async def _run_resume(session_id: str, user_id: str) -> None:
    context = get_or_create_session(session_id, user_id)
    final_status = "completed"
    try:
        async for response in process_resume_request(session_id, user_id=user_id):
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
                message="恢复执行已被用户中断",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        final_status = "error"
        context.last_error = str(exc)
        logger.exception("恢复后台任务错误: %s", exc)
        await _send_and_record(
            session_id,
            MessageFactory.create_error(
                session_id=session_id,
                error_code="RESUME_ERROR",
                error_message=str(exc),
            ),
        )
    finally:
        context.finish_task(final_status)


@router.get("/{session_id}/status")
async def get_session_status(session_id: str) -> dict[str, Any]:
    context = get_or_create_session(session_id)
    snapshot = context.snapshot()
    snapshot["checkpoint"] = await _build_checkpoint_status(context)
    return snapshot


@router.websocket("/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str = "default",
) -> None:
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
                    continue

                if message_type == MessageType.INTERRUPT:
                    context.interrupt()
                    await _send_and_record(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="interrupted",
                            message="已中断当前执行",
                        ),
                    )
                    continue

                if message_type == MessageType.RESUME:
                    if context.current_task and not context.current_task.done():
                        await _send_and_record(
                            session_id,
                            MessageFactory.create_error(
                                session_id=session_id,
                                error_code="TASK_RUNNING",
                                error_message="当前已有任务在执行，无法重复恢复",
                            ),
                        )
                        continue
                    context.reset(clear_analysis_id=False)
                    task = asyncio.create_task(_run_resume(session_id, context.user_id))
                    context.start_task(task)
                    continue

                if message_type == "ping":
                    await _send_and_record(
                        session_id,
                        MessageFactory.create_status(
                            session_id=session_id,
                            status="pong",
                            message="心跳响应",
                        ),
                    )
                    continue

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
            except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
        logger.exception("WebSocket 错误: %s", exc)
        context.interrupt()
        manager.disconnect(session_id)
        sessions.pop(session_id, None)


def reset_sessions() -> None:
    """重置全部会话，供测试使用。"""

    for context in sessions.values():
        context.interrupt()
    sessions.clear()
