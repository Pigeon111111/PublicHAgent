"""WebSocket 消息协议。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型。"""

    USER = "user"
    AGENT = "agent"
    STATUS = "status"
    PROGRESS = "progress"
    ERROR = "error"
    INTERRUPT = "interrupt"
    RESUME = "resume"


class BaseMessage(BaseModel):
    """消息基类。"""

    type: MessageType
    session_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class UserMessage(BaseMessage):
    """用户消息。"""

    type: MessageType = MessageType.USER
    content: str = Field(description="用户输入内容")
    user_id: str = Field(default="default", description="用户 ID")
    context: dict[str, Any] = Field(default_factory=dict, description="上下文信息")


class AgentMessage(BaseMessage):
    """Agent 响应消息。"""

    type: MessageType = MessageType.AGENT
    content: str = Field(description="响应内容")
    intent: str = Field(default="", description="识别出的意图")
    plan: dict[str, Any] | None = Field(default=None, description="执行计划")
    is_streaming: bool = Field(default=False, description="是否为流式输出")
    is_final: bool = Field(default=True, description="是否为最终响应")
    evaluation_report: dict[str, Any] = Field(default_factory=dict, description="评估摘要")
    task_family: str = Field(default="", description="任务家族")
    evaluation_score: float = Field(default=0.0, description="评估得分")
    analysis_id: str = Field(default="", description="分析记录 ID")
    trajectory_id: str = Field(default="", description="轨迹 ID")


class StatusMessage(BaseMessage):
    """状态消息。"""

    type: MessageType = MessageType.STATUS
    status: str = Field(description="状态")
    message: str = Field(default="", description="状态描述")


class ProgressMessage(BaseMessage):
    """进度消息。"""

    type: MessageType = MessageType.PROGRESS
    stage: str = Field(description="当前阶段")
    progress: int = Field(ge=0, le=100, description="进度百分比")
    message: str = Field(default="", description="进度描述")
    details: dict[str, Any] = Field(default_factory=dict, description="详细信息")


class ErrorMessage(BaseMessage):
    """错误消息。"""

    type: MessageType = MessageType.ERROR
    error_code: str = Field(description="错误码")
    error_message: str = Field(description="错误描述")
    details: dict[str, Any] = Field(default_factory=dict, description="错误详情")


class ResumeMessage(BaseMessage):
    """恢复执行消息。"""

    type: MessageType = MessageType.RESUME


class MessageFactory:
    """消息工厂。"""

    @staticmethod
    def create_user_message(
        session_id: str,
        content: str,
        user_id: str = "default",
        context: dict[str, Any] | None = None,
    ) -> UserMessage:
        return UserMessage(
            session_id=session_id,
            content=content,
            user_id=user_id,
            context=context or {},
        )

    @staticmethod
    def create_agent_message(
        session_id: str,
        content: str,
        intent: str = "",
        plan: dict[str, Any] | None = None,
        is_streaming: bool = False,
        is_final: bool = True,
        evaluation_report: dict[str, Any] | None = None,
        task_family: str = "",
        evaluation_score: float = 0.0,
        analysis_id: str = "",
        trajectory_id: str = "",
    ) -> AgentMessage:
        return AgentMessage(
            session_id=session_id,
            content=content,
            intent=intent,
            plan=plan,
            is_streaming=is_streaming,
            is_final=is_final,
            evaluation_report=evaluation_report or {},
            task_family=task_family,
            evaluation_score=evaluation_score,
            analysis_id=analysis_id,
            trajectory_id=trajectory_id,
        )

    @staticmethod
    def create_status(session_id: str, status: str, message: str = "") -> StatusMessage:
        return StatusMessage(session_id=session_id, status=status, message=message)

    @staticmethod
    def create_progress(
        session_id: str,
        stage: str,
        progress: int,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> ProgressMessage:
        return ProgressMessage(
            session_id=session_id,
            stage=stage,
            progress=progress,
            message=message,
            details=details or {},
        )

    @staticmethod
    def create_error(
        session_id: str,
        error_code: str,
        error_message: str,
        details: dict[str, Any] | None = None,
    ) -> ErrorMessage:
        return ErrorMessage(
            session_id=session_id,
            error_code=error_code,
            error_message=error_message,
            details=details or {},
        )


def serialize_message(message: BaseModel) -> str:
    """序列化消息。"""

    return message.model_dump_json()


def deserialize_message(json_str: str) -> BaseModel:
    """反序列化消息。"""

    import json

    data = json.loads(json_str)
    message_type = data.get("type", "")
    message_classes: dict[str, type[BaseModel]] = {
        MessageType.USER: UserMessage,
        MessageType.AGENT: AgentMessage,
        MessageType.STATUS: StatusMessage,
        MessageType.PROGRESS: ProgressMessage,
        MessageType.ERROR: ErrorMessage,
        MessageType.RESUME: ResumeMessage,
    }
    message_class = message_classes.get(message_type, BaseMessage)
    return message_class(**data)


class ProgressTracker:
    """进度追踪器。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._stages: list[dict[str, Any]] = []
        self._current_stage = ""
        self._current_progress = 0

    def start_stage(self, stage: str, message: str = "") -> ProgressMessage:
        self._current_stage = stage
        self._current_progress = 0
        self._stages.append(
            {
                "stage": stage,
                "message": message,
                "start_time": datetime.now().isoformat(),
            }
        )
        return MessageFactory.create_progress(
            session_id=self.session_id,
            stage=stage,
            progress=0,
            message=message,
        )

    def update_progress(
        self,
        progress: int,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> ProgressMessage:
        self._current_progress = min(100, max(0, progress))
        return MessageFactory.create_progress(
            session_id=self.session_id,
            stage=self._current_stage,
            progress=self._current_progress,
            message=message,
            details=details,
        )

    def complete_stage(self, message: str = "") -> ProgressMessage:
        self._current_progress = 100
        if self._stages:
            self._stages[-1]["end_time"] = datetime.now().isoformat()
            self._stages[-1]["completed"] = True
        return MessageFactory.create_progress(
            session_id=self.session_id,
            stage=self._current_stage,
            progress=100,
            message=message or f"{self._current_stage} 完成",
        )

    def get_summary(self) -> dict[str, Any]:
        """返回当前追踪概况。"""

        return {
            "session_id": self.session_id,
            "current_stage": self._current_stage,
            "current_progress": self._current_progress,
            "stages": self._stages,
        }
