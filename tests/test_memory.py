"""记忆管理模块单元测试

测试 MemoryManager 的各项功能。
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.memory.manager import (
    MemoryConfig,
    MemoryManager,
    MemoryResult,
    UserProfile,
)


@pytest.fixture
def temp_persist_dir():
    """创建临时持久化目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def memory_config(temp_persist_dir):
    """创建测试用记忆配置"""
    return MemoryConfig(
        collection_name="test_memories",
        persist_directory=temp_persist_dir,
    )


@pytest.fixture
def mock_memory():
    """创建 mock Memory 实例"""
    mock = MagicMock()
    mock.add.return_value = {
        "results": [
            {
                "id": "test-memory-id-1",
                "memory": "测试记忆内容",
                "event": "ADD",
            }
        ],
        "relations": [],
    }
    mock.search.return_value = {
        "results": [
            {
                "id": "test-memory-id-1",
                "memory": "测试记忆内容",
                "score": 0.95,
                "metadata": {"type": "preference"},
                "user_id": "test_user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }
        ]
    }
    mock.get_all.return_value = {
        "results": [
            {
                "id": "test-memory-id-1",
                "memory": "用户偏好: 喜欢使用 Python 进行数据分析",
                "metadata": {"type": "preference", "category": "programming"},
                "user_id": "test_user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
            {
                "id": "test-memory-id-2",
                "memory": "分析方法: t检验 (上下文: 两组数据比较)",
                "metadata": {"type": "analysis_method", "method": "t检验"},
                "user_id": "test_user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
            {
                "id": "test-memory-id-3",
                "memory": "数据特征: 包含缺失值 (类型: csv)",
                "metadata": {"type": "data_characteristics", "data_type": "csv"},
                "user_id": "test_user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
    }
    mock.update.return_value = {"message": "Memory updated successfully!"}
    mock.delete.return_value = {"message": "Memory deleted successfully!"}
    mock.history.return_value = [
        {
            "id": "history-1",
            "memory_id": "test-memory-id-1",
            "old_memory": None,
            "new_memory": "测试记忆内容",
            "event": "ADD",
        }
    ]
    return mock


class TestMemoryConfig:
    """测试 MemoryConfig 配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = MemoryConfig()
        assert config.collection_name == "pubhagent_memories"
        assert config.persist_directory == "./chroma_db"
        assert config.embedding_model == "text-embedding-3-small"

    def test_custom_config(self):
        """测试自定义配置"""
        config = MemoryConfig(
            collection_name="custom_collection",
            persist_directory="/custom/path",
            embedding_model="custom-model",
        )
        assert config.collection_name == "custom_collection"
        assert config.persist_directory == "/custom/path"
        assert config.embedding_model == "custom-model"


class TestMemoryResult:
    """测试 MemoryResult 数据类"""

    def test_memory_result_creation(self):
        """测试创建记忆结果"""
        result = MemoryResult(
            id="test-id",
            memory="测试内容",
            score=0.95,
            metadata={"key": "value"},
            user_id="test_user",
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
        assert result.id == "test-id"
        assert result.memory == "测试内容"
        assert result.score == 0.95
        assert result.metadata == {"key": "value"}

    def test_memory_result_defaults(self):
        """测试默认值"""
        result = MemoryResult(id="test-id", memory="测试内容")
        assert result.score == 0.0
        assert result.metadata == {}
        assert result.user_id == ""


class TestUserProfile:
    """测试 UserProfile 数据类"""

    def test_user_profile_creation(self):
        """测试创建用户画像"""
        profile = UserProfile(
            user_id="test_user",
            preferences=["偏好1", "偏好2"],
            analysis_methods=["方法1"],
            data_characteristics=["特征1"],
            interaction_history=["历史1"],
        )
        assert profile.user_id == "test_user"
        assert len(profile.preferences) == 2
        assert len(profile.analysis_methods) == 1

    def test_user_profile_defaults(self):
        """测试默认值"""
        profile = UserProfile(user_id="test_user")
        assert profile.preferences == []
        assert profile.analysis_methods == []
        assert profile.data_characteristics == []
        assert profile.interaction_history == []


class TestMemoryManager:
    """测试 MemoryManager 类"""

    @patch("backend.agents.memory.manager.Memory")
    def test_init_memory_manager(self, mock_memory_class, memory_config):
        """测试初始化 MemoryManager"""
        mock_memory_instance = MagicMock()
        mock_memory_class.from_config.return_value = mock_memory_instance

        manager = MemoryManager(config=memory_config)

        assert manager._config == memory_config
        mock_memory_class.from_config.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_build_user_key(self, mock_memory_class, memory_config):
        """测试用户标识键构建"""
        mock_memory_instance = MagicMock()
        mock_memory_class.from_config.return_value = mock_memory_instance

        manager = MemoryManager(config=memory_config)

        assert manager._build_user_key("user1") == "user1"
        assert manager._build_user_key("user1", "session1") == "user1#session1"

    @patch("backend.agents.memory.manager.Memory")
    def test_add_memory_string(self, mock_memory_class, memory_config, mock_memory):
        """测试添加字符串记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.add_memory(
            messages="测试记忆内容",
            user_id="test_user",
        )

        assert "results" in result
        mock_memory.add.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_add_memory_with_session(self, mock_memory_class, memory_config, mock_memory):
        """测试带会话 ID 添加记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.add_memory(
            messages="测试记忆内容",
            user_id="test_user",
            session_id="session1",
        )

        assert "results" in result
        call_args = mock_memory.add.call_args
        assert call_args[1]["user_id"] == "test_user#session1"
        assert call_args[1]["metadata"]["session_id"] == "session1"

    @patch("backend.agents.memory.manager.Memory")
    def test_add_memory_messages_list(self, mock_memory_class, memory_config, mock_memory):
        """测试添加消息列表"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
        ]
        result = manager.add_memory(
            messages=messages,
            user_id="test_user",
        )

        assert "results" in result
        mock_memory.add.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_search_memory(self, mock_memory_class, memory_config, mock_memory):
        """测试搜索记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        results = manager.search_memory(
            query="数据分析",
            user_id="test_user",
            limit=5,
        )

        assert len(results) == 1
        assert isinstance(results[0], MemoryResult)
        assert results[0].id == "test-memory-id-1"
        mock_memory.search.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_update_memory(self, mock_memory_class, memory_config, mock_memory):
        """测试更新记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.update_memory(
            memory_id="test-memory-id-1",
            new_content="更新后的内容",
        )

        assert result["message"] == "Memory updated successfully!"
        mock_memory.update.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_delete_memory(self, mock_memory_class, memory_config, mock_memory):
        """测试删除记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.delete_memory(memory_id="test-memory-id-1")

        assert result["message"] == "Memory deleted successfully!"
        mock_memory.delete.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_get_all_memories(self, mock_memory_class, memory_config, mock_memory):
        """测试获取所有记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        results = manager.get_all_memories(user_id="test_user")

        assert len(results) == 3
        assert all(isinstance(r, MemoryResult) for r in results)
        mock_memory.get_all.assert_called_once()

    @patch("backend.agents.memory.manager.Memory")
    def test_get_memory_history(self, mock_memory_class, memory_config, mock_memory):
        """测试获取记忆历史"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        history = manager.get_memory_history(memory_id="test-memory-id-1")

        assert len(history) == 1
        assert history[0]["event"] == "ADD"
        mock_memory.history.assert_called_once()


class TestUserPreferenceManagement:
    """测试用户偏好管理"""

    @patch("backend.agents.memory.manager.Memory")
    def test_record_user_preference(self, mock_memory_class, memory_config, mock_memory):
        """测试记录用户偏好"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.record_user_preference(
            user_id="test_user",
            preference="喜欢使用 Python 进行数据分析",
            category="programming",
        )

        assert "results" in result
        call_args = mock_memory.add.call_args
        assert "用户偏好" in call_args[0][0]
        assert call_args[1]["metadata"]["type"] == "preference"
        assert call_args[1]["metadata"]["category"] == "programming"

    @patch("backend.agents.memory.manager.Memory")
    def test_record_analysis_method(self, mock_memory_class, memory_config, mock_memory):
        """测试记录分析方法"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.record_analysis_method(
            user_id="test_user",
            method="t检验",
            context="两组数据比较",
        )

        assert "results" in result
        call_args = mock_memory.add.call_args
        assert "分析方法" in call_args[0][0]
        assert call_args[1]["metadata"]["type"] == "analysis_method"

    @patch("backend.agents.memory.manager.Memory")
    def test_record_data_characteristics(self, mock_memory_class, memory_config, mock_memory):
        """测试记录数据特征"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        result = manager.record_data_characteristics(
            user_id="test_user",
            characteristics="包含缺失值",
            data_type="csv",
        )

        assert "results" in result
        call_args = mock_memory.add.call_args
        assert "数据特征" in call_args[0][0]
        assert call_args[1]["metadata"]["type"] == "data_characteristics"


class TestUserProfileRetrieval:
    """测试用户画像获取"""

    @patch("backend.agents.memory.manager.Memory")
    def test_get_user_profile(self, mock_memory_class, memory_config, mock_memory):
        """测试获取用户画像"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        profile = manager.get_user_profile(user_id="test_user")

        assert isinstance(profile, UserProfile)
        assert profile.user_id == "test_user"
        assert len(profile.preferences) == 1
        assert len(profile.analysis_methods) == 1
        assert len(profile.data_characteristics) == 1

    @patch("backend.agents.memory.manager.Memory")
    def test_get_relevant_memories_for_planning(self, mock_memory_class, memory_config, mock_memory):
        """测试获取规划相关记忆摘要"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        summary = manager.get_relevant_memories_for_planning(
            user_id="test_user",
            query="数据分析",
            token_budget=500,
        )

        assert isinstance(summary, str)
        assert len(summary) > 0

    @patch("backend.agents.memory.manager.Memory")
    def test_get_relevant_memories_with_token_budget(self, mock_memory_class, memory_config, mock_memory):
        """测试 Token 预算限制"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)

        summary = manager.get_relevant_memories_for_planning(
            user_id="test_user",
            query="数据分析",
            token_budget=10,
        )

        assert len(summary) <= 40


class TestClearUserMemories:
    """测试清除用户记忆"""

    @patch("backend.agents.memory.manager.Memory")
    def test_clear_user_memories(self, mock_memory_class, memory_config, mock_memory):
        """测试清除用户所有记忆"""
        mock_memory_class.from_config.return_value = mock_memory

        manager = MemoryManager(config=memory_config)
        manager.clear_user_memories(user_id="test_user")

        assert mock_memory.delete.call_count == 3
