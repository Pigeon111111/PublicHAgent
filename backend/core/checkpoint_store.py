"""LangGraph 持久化检查点管理。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ImportError:
    AsyncSqliteSaver = None  # type: ignore[assignment,misc]


class WorkflowCheckpointManager:
    """管理工作流持久化检查点。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else Path("data/checkpoints/langgraph.db")
        self._saver: Any | None = None
        self._backend = "memory"
        self._context_manager: Any | None = None
        self._loop_id: int | None = None
        self._lock = asyncio.Lock()

    async def get_checkpointer(self) -> Any:
        """获取持久化 checkpointer。"""
        current_loop_id = id(asyncio.get_running_loop())
        if self._saver is not None and self._loop_id == current_loop_id:
            return self._saver

        async with self._lock:
            if self._saver is not None and self._loop_id == current_loop_id:
                return self._saver

            if self._loop_id is not None and self._loop_id != current_loop_id:
                self._context_manager = None
                self._saver = None

            if AsyncSqliteSaver is None:
                self._backend = "memory"
                self._loop_id = current_loop_id
                self._saver = MemorySaver()
                return self._saver

            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            context_manager = AsyncSqliteSaver.from_conn_string(str(self._db_path))
            saver = await context_manager.__aenter__()
            await saver.setup()
            self._context_manager = context_manager
            self._backend = "sqlite"
            self._loop_id = current_loop_id
            self._saver = saver
            return self._saver

    async def close(self) -> None:
        """关闭持久化连接。"""
        if self._context_manager is not None:
            await self._context_manager.__aexit__(None, None, None)
        self._context_manager = None
        self._saver = None
        self._loop_id = None

    def snapshot(self) -> dict[str, Any]:
        """返回当前检查点管理状态。"""
        return {
            "backend": self._backend,
            "db_path": str(self._db_path),
            "initialized": self._saver is not None,
        }


_checkpoint_manager: WorkflowCheckpointManager | None = None


def get_workflow_checkpoint_manager() -> WorkflowCheckpointManager:
    """获取全局检查点管理器。"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = WorkflowCheckpointManager()
    return _checkpoint_manager


async def close_workflow_checkpoint_manager() -> None:
    """关闭全局检查点管理器。"""
    global _checkpoint_manager
    if _checkpoint_manager is not None:
        await _checkpoint_manager.close()
        _checkpoint_manager = None
