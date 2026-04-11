"""历史记录、评估详情与重跑接口。"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.deps import Pagination
from backend.learning.skill_learning import SkillLearningService
from backend.storage.history_storage import get_history_storage
from backend.storage.history_storage import reset_history_storage as reset_history_storage_db

router = APIRouter()


class Message(BaseModel):
    """对话消息。"""

    role: str = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    timestamp: str = Field(default="", description="时间戳")


class Conversation(BaseModel):
    """对话详情。"""

    id: str
    title: str
    messages: list[Message]
    created_at: str
    updated_at: str
    message_count: int


class ConversationListResponse(BaseModel):
    """对话列表响应。"""

    conversations: list[Conversation]
    total: int


class EvaluationSummary(BaseModel):
    """评估摘要。"""

    id: str = ""
    task_family: str = ""
    final_score: float = 0.0
    passed: bool = False
    summary: str = ""
    review_status: str = "unreviewed"


class AnalysisRecord(BaseModel):
    """分析记录。"""

    id: str
    session_id: str | None = None
    conversation_id: str | None = None
    query: str
    intent: str
    status: str
    result_summary: str
    created_at: str
    updated_at: str
    steps_count: int
    trajectory_id: str = ""
    evaluation_id: str = ""
    task_family: str = ""
    evaluation_score: float = 0.0
    evaluation_passed: bool = False
    evaluation_summary: str = ""
    review_status: str = "unreviewed"


class AnalysisHistoryResponse(BaseModel):
    """分析历史响应。"""

    records: list[AnalysisRecord]
    total: int


class MetricAssertionPayload(BaseModel):
    """指标断言。"""

    metric: str
    expected: Any = None
    actual: Any = None
    passed: bool
    tolerance: str = ""


class EvaluationFindingPayload(BaseModel):
    """评估发现。"""

    severity: str
    category: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationScoreBreakdownPayload(BaseModel):
    """分项得分。"""

    artifact_score: float = 0.0
    statistical_score: float = 0.0
    process_score: float = 0.0
    report_score: float = 0.0


class EvaluationReportPayload(BaseModel):
    """完整评估报告。"""

    id: str
    analysis_record_id: str
    session_id: str | None = None
    trajectory_id: str = ""
    task_family: str = ""
    final_score: float = 0.0
    passed: bool = False
    summary: str = ""
    report_json: dict[str, Any] = Field(default_factory=dict)
    review_status: str = "unreviewed"
    review_label: str = ""
    review_comment: str = ""
    reviewed_by: str = ""
    associated_skill: str = ""
    created_at: str
    updated_at: str


class AnalysisDetailResponse(BaseModel):
    """分析详情响应。"""

    record: AnalysisRecord
    evaluation: EvaluationReportPayload | None = None


class EvaluationReviewRequest(BaseModel):
    """评估审阅请求。"""

    review_status: Literal["unreviewed", "confirmed", "disputed", "needs_followup"]
    review_label: Literal["correct", "false_positive", "false_negative", "metric_mismatch", "report_mismatch"]
    review_comment: str = ""
    reviewed_by: str = "default"


class RerunResponse(BaseModel):
    """重跑准备响应。"""

    analysis_id: str
    session_id: str
    query: str
    resume_available: bool = False


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    pagination: Pagination,
    user_id: str = "default",
) -> ConversationListResponse:
    storage = get_history_storage()
    conversations, total = storage.list_conversations(
        user_id=user_id,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ConversationListResponse(
        conversations=[Conversation(**conversation) for conversation in conversations],
        total=total,
    )


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str) -> Conversation:
    storage = get_history_storage()
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        )
    return Conversation(**conversation)


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    title: str = "新对话",
    user_id: str = "default",
) -> Conversation:
    storage = get_history_storage()
    conversation = storage.create_conversation(title=title, user_id=user_id)
    return Conversation(**conversation)


@router.post("/conversations/{conversation_id}/messages", response_model=Message)
async def add_message(
    conversation_id: str,
    role: str,
    content: str,
) -> Message:
    storage = get_history_storage()
    try:
        message = storage.add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        ) from exc
    return Message(**message)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str) -> None:
    storage = get_history_storage()
    if not storage.delete_conversation(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        )


@router.get("/analysis", response_model=AnalysisHistoryResponse)
async def get_analysis_history(
    pagination: Pagination,
    user_id: str = "default",
) -> AnalysisHistoryResponse:
    storage = get_history_storage()
    records, total = storage.list_analysis_records(
        user_id=user_id,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return AnalysisHistoryResponse(
        records=[AnalysisRecord(**record) for record in records],
        total=total,
    )


@router.get("/analysis/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis_detail(analysis_id: str) -> AnalysisDetailResponse:
    storage = get_history_storage()
    record = storage.get_analysis_record(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"分析记录不存在: {analysis_id}")
    evaluation = storage.get_evaluation_report(analysis_id)
    return AnalysisDetailResponse(
        record=AnalysisRecord(**record),
        evaluation=EvaluationReportPayload(**evaluation) if evaluation is not None else None,
    )


@router.post("/analysis", response_model=AnalysisRecord, status_code=status.HTTP_201_CREATED)
async def create_analysis_record(
    query: str,
    intent: str,
    status: str = "pending",
    result_summary: str = "",
    steps_count: int = 0,
    user_id: str = "default",
) -> AnalysisRecord:
    storage = get_history_storage()
    record = storage.create_analysis_record(
        query=query,
        intent=intent,
        status=status,
        result_summary=result_summary,
        steps_count=steps_count,
        user_id=user_id,
    )
    return AnalysisRecord(**record)


@router.get("/analysis/{analysis_id}/evaluation", response_model=EvaluationReportPayload)
async def get_analysis_evaluation(analysis_id: str) -> EvaluationReportPayload:
    storage = get_history_storage()
    evaluation = storage.get_evaluation_report(analysis_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"评估报告不存在: {analysis_id}")
    return EvaluationReportPayload(**evaluation)


@router.post("/analysis/{analysis_id}/evaluation/review", response_model=EvaluationReportPayload)
async def review_analysis_evaluation(
    analysis_id: str,
    request: EvaluationReviewRequest,
) -> EvaluationReportPayload:
    storage = get_history_storage()
    evaluation = storage.update_evaluation_review(
        analysis_id,
        review_status=request.review_status,
        review_label=request.review_label,
        review_comment=request.review_comment,
        reviewed_by=request.reviewed_by,
    )
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"评估报告不存在: {analysis_id}")
    if request.review_status == "disputed" and evaluation.get("associated_skill"):
        with suppress(Exception):
            SkillLearningService().demote_skill(str(evaluation["associated_skill"]))
    return EvaluationReportPayload(**evaluation)


@router.post("/analysis/{analysis_id}/rerun", response_model=RerunResponse)
async def rerun_analysis(analysis_id: str) -> RerunResponse:
    storage = get_history_storage()
    record = storage.get_analysis_record(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"分析记录不存在: {analysis_id}")
    session_id = str(record.get("session_id") or f"session_rerun_{analysis_id}")
    return RerunResponse(
        analysis_id=analysis_id,
        session_id=session_id,
        query=str(record.get("query") or ""),
        resume_available=bool(record.get("status") == "interrupted"),
    )


def reset_history_storage() -> None:
    """供测试重置历史存储。"""

    reset_history_storage_db()
