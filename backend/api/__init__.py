"""API 层模块

提供 FastAPI 应用、WebSocket 网关、REST API 和流式输出协议。
"""

from backend.api.deps import (
    LLMClientDep,
    MemoryManagerDep,
    Pagination,
    PaginationParams,
    SessionContext,
    ToolRegistryDep,
    UploadDir,
    ValidatedUploadFile,
    get_llm_client_dep,
    get_memory_manager,
    get_pagination,
    get_tool_registry_dep,
    get_upload_dir,
    reset_dependencies,
    validate_upload_file,
)
from backend.api.main import APIError, AppSettings, app, create_app, get_settings
from backend.api.protocol import (
    AgentMessage,
    BaseMessage,
    ErrorMessage,
    MessageFactory,
    MessageType,
    ProgressMessage,
    ProgressTracker,
    StatusMessage,
    UserMessage,
    deserialize_message,
    serialize_message,
)
from backend.api.websocket import (
    ConnectionManager,
    get_or_create_session,
    manager,
    reset_sessions,
)
from backend.api.websocket import (
    SessionContext as WSSessionContext,
)
from backend.api.websocket import (
    router as websocket_router,
)

__all__ = [
    "APIError",
    "AppSettings",
    "AgentMessage",
    "BaseMessage",
    "ConnectionManager",
    "ErrorMessage",
    "LLMClientDep",
    "MemoryManagerDep",
    "MessageFactory",
    "MessageType",
    "Pagination",
    "PaginationParams",
    "ProgressMessage",
    "ProgressTracker",
    "SessionContext",
    "StatusMessage",
    "ToolRegistryDep",
    "UploadDir",
    "UserMessage",
    "ValidatedUploadFile",
    "WSSessionContext",
    "app",
    "create_app",
    "deserialize_message",
    "get_llm_client_dep",
    "get_memory_manager",
    "get_or_create_session",
    "get_pagination",
    "get_settings",
    "get_tool_registry_dep",
    "get_upload_dir",
    "manager",
    "reset_dependencies",
    "reset_sessions",
    "serialize_message",
    "validate_upload_file",
    "websocket_router",
]
