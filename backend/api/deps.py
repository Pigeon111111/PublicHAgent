"""依赖注入模块

提供 FastAPI 依赖注入函数，包括 LLM 客户端、记忆管理器、工具注册表等。
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.agents.base.llm_client import LLMClient, get_llm_client
from backend.agents.memory.manager import MemoryConfig, MemoryManager
from backend.tools.registry import ToolRegistry, get_tool_registry


class SessionContext(BaseModel):
    """会话上下文"""

    session_id: str
    user_id: str = "default"


@lru_cache
def get_llm_client_dep() -> LLMClient:
    """获取 LLM 客户端依赖"""
    return get_llm_client()


@lru_cache
def get_memory_manager() -> MemoryManager:
    """获取记忆管理器依赖"""
    config = MemoryConfig(
        collection_name="pubhagent_memories",
        persist_directory="./chroma_db",
    )
    return MemoryManager(config=config)


@lru_cache
def get_tool_registry_dep() -> ToolRegistry:
    """获取工具注册表依赖"""
    return get_tool_registry()


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client_dep)]
MemoryManagerDep = Annotated[MemoryManager, Depends(get_memory_manager)]
ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry_dep)]


ALLOWED_EXTENSIONS = {
    "csv", "xlsx", "xls", "json", "txt", "parquet", "feather",
    "png", "jpg", "jpeg", "gif", "svg",
    "pdf", "docx", "doc",
}
MAX_FILE_SIZE = 50 * 1024 * 1024


async def validate_upload_file(file: UploadFile) -> UploadFile:
    """验证上传文件

    Args:
        file: 上传的文件

    Returns:
        验证通过的文件

    Raises:
        HTTPException: 文件验证失败
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    extension = file.filename.split(".")[-1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {extension}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制 ({MAX_FILE_SIZE // (1024 * 1024)}MB)",
        )

    await file.seek(0)
    return file


ValidatedUploadFile = Annotated[UploadFile, Depends(validate_upload_file)]


def get_upload_dir() -> Path:
    """获取上传目录路径"""
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


UploadDir = Annotated[Path, Depends(get_upload_dir)]


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination(
    page: int = 1,
    page_size: int = 20,
) -> PaginationParams:
    """获取分页参数"""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


def reset_dependencies() -> None:
    """重置所有依赖缓存（用于测试）"""
    get_llm_client_dep.cache_clear()
    get_memory_manager.cache_clear()
    get_tool_registry_dep.cache_clear()
