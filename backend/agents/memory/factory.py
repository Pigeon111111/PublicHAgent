"""MemoryManager 工厂。"""

from __future__ import annotations

import os

from backend.agents.memory.manager import MemoryConfig, MemoryManager
from backend.storage.user_config_storage import get_user_config_storage

_memory_managers: dict[str, MemoryManager | None] = {}


def get_optional_memory_manager(user_id: str = "default") -> MemoryManager | None:
    """按用户获取可用的 MemoryManager。"""
    if user_id in _memory_managers and _memory_managers[user_id] is not None:
        return _memory_managers[user_id]

    api_key = os.getenv("OPENAI_API_KEY")
    try:
        user_config = get_user_config_storage().get(user_id)
        if user_config and user_config.api_keys.openai:
            api_key = user_config.api_keys.openai
    except Exception:
        pass

    if not api_key:
        return None

    try:
        manager = MemoryManager(
            config=MemoryConfig(
                collection_name="pubhagent_memories",
                persist_directory="./chroma_db",
            ),
            api_key=api_key,
        )
    except Exception:
        manager = None

    if manager is not None:
        _memory_managers[user_id] = manager
    return manager


def reset_memory_manager_cache() -> None:
    """清理缓存，供测试使用。"""
    _memory_managers.clear()
