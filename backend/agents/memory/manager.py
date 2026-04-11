"""记忆管理器实现

基于 mem0 库实现智能记忆管理，支持 ChromaDB 向量存储和用户隔离。
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    from mem0 import Memory
except ImportError:
    Memory = None


class MemoryConfig(BaseModel):
    """记忆系统配置"""

    collection_name: str = Field(default="pubhagent_memories", description="ChromaDB 集合名称")
    persist_directory: str = Field(default="./chroma_db", description="向量数据库持久化目录")
    embedding_model: str = Field(default="text-embedding-3-small", description="嵌入模型")


class MemoryResult(BaseModel):
    """记忆搜索结果"""

    id: str = Field(description="记忆 ID")
    memory: str = Field(description="记忆内容")
    score: float = Field(default=0.0, description="相关性分数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    user_id: str = Field(default="", description="用户 ID")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class UserProfile(BaseModel):
    """用户画像"""

    user_id: str = Field(description="用户 ID")
    preferences: list[str] = Field(default_factory=list, description="用户偏好")
    analysis_methods: list[str] = Field(default_factory=list, description="常用分析方法")
    data_characteristics: list[str] = Field(default_factory=list, description="数据特征")
    interaction_history: list[str] = Field(default_factory=list, description="交互历史摘要")


class MemoryManager:
    """记忆管理器

    基于 mem0 实现智能记忆管理，支持：
    - ChromaDB 向量存储
    - 用户隔离（user_id + session_id）
    - 用户画像管理
    """

    def __init__(
        self,
        config: MemoryConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        """初始化记忆管理器

        Args:
            config: 记忆配置
            api_key: OpenAI API Key（用于嵌入模型）
        """
        if Memory is None:
            raise ImportError("mem0ai 未安装，请运行: pip install mem0ai")

        self._config = config or MemoryConfig()
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")

        self._persist_dir = Path(self._config.persist_directory)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._memory = self._init_memory()

    def _init_memory(self) -> Memory:
        """初始化 mem0 Memory 实例"""
        if self._api_key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = self._api_key

        mem0_config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": self._config.collection_name,
                    "path": str(self._persist_dir),
                },
            },
        }

        return Memory.from_config(mem0_config)

    def _build_user_key(self, user_id: str, session_id: str | None = None) -> str:
        """构建用户标识键

        Args:
            user_id: 用户 ID
            session_id: 会话 ID

        Returns:
            用户标识键
        """
        if session_id:
            return f"{user_id}#{session_id}"
        return user_id

    def add_memory(
        self,
        messages: str | list[dict[str, str]],
        user_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """添加记忆

        Args:
            messages: 消息内容，可以是字符串或消息列表
            user_id: 用户 ID
            session_id: 会话 ID（可选）
            metadata: 元数据

        Returns:
            添加结果
        """
        user_key = self._build_user_key(user_id, session_id)

        enriched_metadata = metadata or {}
        if session_id:
            enriched_metadata["session_id"] = session_id

        result = self._memory.add(
            messages,
            user_id=user_key,
            metadata=enriched_metadata,
        )

        return dict(result)

    def search_memory(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        session_id: str | None = None,
    ) -> list[MemoryResult]:
        """搜索记忆

        Args:
            query: 查询字符串
            user_id: 用户 ID
            limit: 返回结果数量限制
            session_id: 会话 ID（可选）

        Returns:
            记忆搜索结果列表
        """
        user_key = self._build_user_key(user_id, session_id)

        results = self._memory.search(
            query,
            user_id=user_key,
            limit=limit,
        )

        memory_results = []
        for item in results.get("results", []):
            memory_results.append(
                MemoryResult(
                    id=item.get("id", ""),
                    memory=item.get("memory", ""),
                    score=item.get("score", 0.0),
                    metadata=item.get("metadata", {}),
                    user_id=item.get("user_id", ""),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )

        return memory_results

    def update_memory(
        self,
        memory_id: str,
        new_content: str,
    ) -> dict[str, Any]:
        """更新记忆

        Args:
            memory_id: 记忆 ID
            new_content: 新内容

        Returns:
            更新结果
        """
        result = self._memory.update(
            memory_id=memory_id,
            data=new_content,
        )
        return dict(result)

    def delete_memory(self, memory_id: str) -> dict[str, Any]:
        """删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            删除结果
        """
        result = self._memory.delete(memory_id=memory_id)
        return dict(result)

    def get_all_memories(
        self,
        user_id: str,
        session_id: str | None = None,
    ) -> list[MemoryResult]:
        """获取用户所有记忆

        Args:
            user_id: 用户 ID
            session_id: 会话 ID（可选）

        Returns:
            记忆列表
        """
        user_key = self._build_user_key(user_id, session_id)

        results = self._memory.get_all(user_id=user_key)

        memory_results = []
        for item in results.get("results", []):
            memory_results.append(
                MemoryResult(
                    id=item.get("id", ""),
                    memory=item.get("memory", ""),
                    score=0.0,
                    metadata=item.get("metadata", {}),
                    user_id=item.get("user_id", ""),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )

        return memory_results

    def get_memory_history(self, memory_id: str) -> list[dict[str, Any]]:
        """获取记忆历史

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆历史列表
        """
        history = self._memory.history(memory_id=memory_id)
        return [dict(item) for item in history]

    def record_user_preference(
        self,
        user_id: str,
        preference: str,
        category: str = "general",
    ) -> dict[str, Any]:
        """记录用户偏好

        Args:
            user_id: 用户 ID
            preference: 偏好描述
            category: 偏好类别

        Returns:
            添加结果
        """
        return self.add_memory(
            messages=f"用户偏好: {preference}",
            user_id=user_id,
            metadata={
                "type": "preference",
                "category": category,
            },
        )

    def record_analysis_method(
        self,
        user_id: str,
        method: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """记录常用分析方法

        Args:
            user_id: 用户 ID
            method: 分析方法名称
            context: 使用上下文

        Returns:
            添加结果
        """
        content = f"分析方法: {method}"
        if context:
            content += f" (上下文: {context})"

        return self.add_memory(
            messages=content,
            user_id=user_id,
            metadata={
                "type": "analysis_method",
                "method": method,
            },
        )

    def record_data_characteristics(
        self,
        user_id: str,
        characteristics: str,
        data_type: str | None = None,
    ) -> dict[str, Any]:
        """记录数据特征

        Args:
            user_id: 用户 ID
            characteristics: 数据特征描述
            data_type: 数据类型

        Returns:
            添加结果
        """
        content = f"数据特征: {characteristics}"
        if data_type:
            content += f" (类型: {data_type})"

        return self.add_memory(
            messages=content,
            user_id=user_id,
            metadata={
                "type": "data_characteristics",
                "data_type": data_type,
            },
        )

    def get_user_profile(self, user_id: str) -> UserProfile:
        """获取用户画像

        Args:
            user_id: 用户 ID

        Returns:
            用户画像
        """
        all_memories = self.get_all_memories(user_id)

        preferences = []
        analysis_methods = []
        data_characteristics = []
        interaction_history = []

        for mem in all_memories:
            metadata = mem.metadata
            mem_type = metadata.get("type", "")
            content = mem.memory

            if mem_type == "preference":
                preferences.append(content)
            elif mem_type == "analysis_method":
                analysis_methods.append(content)
            elif mem_type == "data_characteristics":
                data_characteristics.append(content)
            else:
                interaction_history.append(content)

        return UserProfile(
            user_id=user_id,
            preferences=preferences,
            analysis_methods=analysis_methods,
            data_characteristics=data_characteristics,
            interaction_history=interaction_history[-10:],
        )

    def get_relevant_memories_for_planning(
        self,
        user_id: str,
        query: str,
        token_budget: int = 500,
    ) -> str:
        """获取与规划相关的记忆摘要

        Args:
            user_id: 用户 ID
            query: 当前查询
            token_budget: Token 预算

        Returns:
            记忆摘要字符串
        """
        profile = self.get_user_profile(user_id)

        relevant_memories = self.search_memory(
            query=query,
            user_id=user_id,
            limit=5,
        )

        summary_parts = []

        if profile.preferences:
            summary_parts.append("用户偏好:\n" + "\n".join(f"- {p}" for p in profile.preferences[:5]))

        if profile.analysis_methods:
            summary_parts.append("常用分析方法:\n" + "\n".join(f"- {m}" for m in profile.analysis_methods[:5]))

        if relevant_memories:
            summary_parts.append(
                "相关历史记忆:\n" + "\n".join(f"- {m.memory}" for m in relevant_memories[:3])
            )

        summary = "\n\n".join(summary_parts)

        estimated_tokens = len(summary) // 4
        if estimated_tokens > token_budget:
            summary = summary[: token_budget * 4]

        return summary if summary else "暂无相关历史记忆"

    def clear_user_memories(self, user_id: str) -> None:
        """清除用户所有记忆

        Args:
            user_id: 用户 ID
        """
        all_memories = self.get_all_memories(user_id)
        for mem in all_memories:
            self.delete_memory(mem.id)
