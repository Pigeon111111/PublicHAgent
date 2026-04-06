"""历史记录路由

提供对话历史、分析历史等接口。
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.deps import Pagination

router = APIRouter()


class Message(BaseModel):
    """消息"""

    role: str = Field(description="角色: user/assistant/system")
    content: str = Field(description="消息内容")
    timestamp: str = Field(default="", description="时间戳")


class Conversation(BaseModel):
    """对话"""

    id: str
    title: str
    messages: list[Message]
    created_at: str
    updated_at: str
    message_count: int


class ConversationListResponse(BaseModel):
    """对话列表响应"""

    conversations: list[Conversation]
    total: int


class AnalysisRecord(BaseModel):
    """分析记录"""

    id: str
    query: str
    intent: str
    status: str
    result_summary: str
    created_at: str
    steps_count: int


class AnalysisHistoryResponse(BaseModel):
    """分析历史响应"""

    records: list[AnalysisRecord]
    total: int


_in_memory_conversations: dict[str, Conversation] = {}
_in_memory_analysis_history: dict[str, list[AnalysisRecord]] = {}


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    pagination: Pagination,
    user_id: str = "default",
) -> ConversationListResponse:
    """获取对话列表

    Args:
        pagination: 分页参数
        user_id: 用户 ID

    Returns:
        对话列表
    """
    user_conversations = [
        conv for conv in _in_memory_conversations.values()
        if conv.id.startswith(user_id)
    ]

    user_conversations.sort(key=lambda x: x.updated_at, reverse=True)

    total = len(user_conversations)
    start = pagination.offset
    end = start + pagination.limit
    paginated = user_conversations[start:end]

    return ConversationListResponse(conversations=paginated, total=total)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: str,
) -> Conversation:
    """获取对话详情

    Args:
        conversation_id: 对话 ID

    Returns:
        对话详情
    """
    if conversation_id not in _in_memory_conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        )

    return _in_memory_conversations[conversation_id]


@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    title: str = "新对话",
    user_id: str = "default",
) -> Conversation:
    """创建新对话

    Args:
        title: 对话标题
        user_id: 用户 ID

    Returns:
        创建的对话
    """
    timestamp = datetime.now().isoformat()
    conversation_id = f"{user_id}_{timestamp}"

    conversation = Conversation(
        id=conversation_id,
        title=title,
        messages=[],
        created_at=timestamp,
        updated_at=timestamp,
        message_count=0,
    )

    _in_memory_conversations[conversation_id] = conversation
    return conversation


@router.post("/conversations/{conversation_id}/messages", response_model=Message)
async def add_message(
    conversation_id: str,
    role: str,
    content: str,
) -> Message:
    """添加消息到对话

    Args:
        conversation_id: 对话 ID
        role: 角色
        content: 消息内容

    Returns:
        添加的消息
    """
    if conversation_id not in _in_memory_conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        )

    timestamp = datetime.now().isoformat()
    message = Message(role=role, content=content, timestamp=timestamp)

    conversation = _in_memory_conversations[conversation_id]
    conversation.messages.append(message)
    conversation.message_count = len(conversation.messages)
    conversation.updated_at = timestamp

    return message


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
) -> None:
    """删除对话

    Args:
        conversation_id: 对话 ID
    """
    if conversation_id not in _in_memory_conversations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"对话不存在: {conversation_id}",
        )

    del _in_memory_conversations[conversation_id]


@router.get("/analysis", response_model=AnalysisHistoryResponse)
async def get_analysis_history(
    pagination: Pagination,
    user_id: str = "default",
) -> AnalysisHistoryResponse:
    """获取分析历史

    Args:
        pagination: 分页参数
        user_id: 用户 ID
        memory_manager: 记忆管理器

    Returns:
        分析历史
    """
    records = _in_memory_analysis_history.get(user_id, [])

    total = len(records)
    start = pagination.offset
    end = start + pagination.limit
    paginated = records[start:end]

    return AnalysisHistoryResponse(records=paginated, total=total)


@router.post("/analysis", response_model=AnalysisRecord, status_code=status.HTTP_201_CREATED)
async def create_analysis_record(
    query: str,
    intent: str,
    status: str = "pending",
    result_summary: str = "",
    steps_count: int = 0,
    user_id: str = "default",
) -> AnalysisRecord:
    """创建分析记录

    Args:
        query: 查询内容
        intent: 意图
        status: 状态
        result_summary: 结果摘要
        steps_count: 步骤数
        user_id: 用户 ID

    Returns:
        创建的分析记录
    """
    timestamp = datetime.now().isoformat()
    record_id = f"analysis_{timestamp}"

    record = AnalysisRecord(
        id=record_id,
        query=query,
        intent=intent,
        status=status,
        result_summary=result_summary,
        created_at=timestamp,
        steps_count=steps_count,
    )

    if user_id not in _in_memory_analysis_history:
        _in_memory_analysis_history[user_id] = []
    _in_memory_analysis_history[user_id].append(record)

    return record


def reset_history_storage() -> None:
    """重置历史存储（用于测试）"""
    global _in_memory_conversations, _in_memory_analysis_history
    _in_memory_conversations = {}
    _in_memory_analysis_history = {}
