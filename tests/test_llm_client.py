"""LLM 客户端单元测试"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from backend.agents.base.llm_client import (
    LLMClient,
    LLMClientError,
    ModelConfig,
    ModelsConfig,
    get_llm_client,
)


@pytest.fixture
def sample_config() -> dict:
    """创建示例配置"""
    return {
        "models": [
            {
                "id": "test-model",
                "name": "Test Model",
                "provider": "openai",
                "base_url": "https://api.test.com/v1",
                "api_key_env": "TEST_API_KEY",
                "max_tokens": 2048,
                "temperature": 0.5,
                "supports_streaming": True,
                "supports_function_calling": True,
            }
        ],
        "default_model": "test-model",
        "fallback_model": "test-model",
    }


@pytest.fixture
def config_file(tmp_path: Path, sample_config: dict) -> Path:
    """创建临时配置文件"""
    config_path = tmp_path / "models.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(sample_config, f)
    return config_path


class TestModelConfig:
    """测试 ModelConfig"""

    def test_model_config_creation(self) -> None:
        """测试模型配置创建"""
        config = ModelConfig(
            id="gpt-4",
            name="GPT-4",
            provider="openai",
            api_key_env="OPENAI_API_KEY",
        )
        assert config.id == "gpt-4"
        assert config.name == "GPT-4"
        assert config.provider == "openai"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_model_config_with_custom_values(self) -> None:
        """测试自定义值的模型配置"""
        config = ModelConfig(
            id="custom-model",
            name="Custom Model",
            provider="anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=8192,
            temperature=0.3,
        )
        assert config.max_tokens == 8192
        assert config.temperature == 0.3


class TestModelsConfig:
    """测试 ModelsConfig"""

    def test_models_config_creation(self, sample_config: dict) -> None:
        """测试模型配置集合创建"""
        config = ModelsConfig(**sample_config)
        assert len(config.models) == 1
        assert config.default_model == "test-model"
        assert config.fallback_model == "test-model"


class TestLLMClient:
    """测试 LLMClient"""

    def test_init_with_config_path(self, config_file: Path) -> None:
        """测试使用配置路径初始化"""
        LLMClient.reset()
        client = LLMClient(config_file)
        assert client._config_path == config_file

    def test_load_config(self, config_file: Path) -> None:
        """测试加载配置"""
        LLMClient.reset()
        client = LLMClient(config_file)
        assert client._config is not None
        assert len(client._config.models) == 1

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """测试配置文件不存在"""
        LLMClient.reset()
        with pytest.raises(LLMClientError, match="配置文件不存在"):
            LLMClient(tmp_path / "nonexistent.json")

    def test_get_model_config(self, config_file: Path) -> None:
        """测试获取模型配置"""
        LLMClient.reset()
        client = LLMClient(config_file)
        model_config = client.get_model_config("test-model")
        assert model_config.id == "test-model"
        assert model_config.provider == "openai"

    def test_get_model_config_not_found(self, config_file: Path) -> None:
        """测试获取不存在的模型配置"""
        LLMClient.reset()
        client = LLMClient(config_file)
        with pytest.raises(LLMClientError, match="模型不存在"):
            client.get_model_config("nonexistent-model")

    def test_get_llm_api_key_not_set(self, config_file: Path) -> None:
        """测试 API Key 未设置"""
        LLMClient.reset()
        client = LLMClient(config_file)
        with pytest.raises(LLMClientError, match="API Key 未配置"):
            client.get_llm("test-model")

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatOpenAI")
    def test_get_llm_openai(
        self, mock_chat_openai: MagicMock, config_file: Path
    ) -> None:
        """测试获取 OpenAI LLM"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(config_file)
        llm = client.get_llm("test-model")

        assert llm == mock_llm
        mock_chat_openai.assert_called_once()

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatOpenAI")
    def test_get_llm_singleton_cache(
        self, mock_chat_openai: MagicMock, config_file: Path
    ) -> None:
        """测试单例缓存机制"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(config_file)

        llm1 = client.get_llm("test-model")
        llm2 = client.get_llm("test-model")

        assert llm1 is llm2
        mock_chat_openai.assert_called_once()

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatOpenAI")
    def test_get_default_llm(
        self, mock_chat_openai: MagicMock, config_file: Path
    ) -> None:
        """测试获取默认 LLM"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(config_file)
        llm = client.get_default_llm()

        assert llm == mock_llm

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatOpenAI")
    def test_get_fallback_llm(
        self, mock_chat_openai: MagicMock, config_file: Path
    ) -> None:
        """测试获取备用 LLM"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(config_file)
        llm = client.get_fallback_llm()

        assert llm == mock_llm

    def test_clear_cache(self, config_file: Path) -> None:
        """测试清除缓存"""
        LLMClient.reset()
        client = LLMClient(config_file)
        client._instances["test"] = MagicMock()
        client.clear_cache()
        assert len(client._instances) == 0

    @patch.dict(os.environ, {"TEST_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatOpenAI")
    def test_invoke_with_retry(
        self, mock_chat_openai: MagicMock, config_file: Path
    ) -> None:
        """测试带重试的调用"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_llm.ainvoke = AsyncMock(return_value="response")
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(config_file)

        import asyncio

        result = asyncio.run(client.invoke_with_retry("test-model", []))

        assert result == "response"


class TestGetLLMClient:
    """测试 get_llm_client 工厂函数"""

    def test_get_llm_client(self, config_file: Path) -> None:
        """测试获取 LLM 客户端"""
        LLMClient.reset()
        client = get_llm_client(config_file)
        assert isinstance(client, LLMClient)


class TestAnthropicProvider:
    """测试 Anthropic 提供商"""

    @pytest.fixture
    def anthropic_config(self, tmp_path: Path) -> Path:
        """创建 Anthropic 配置文件"""
        config = {
            "models": [
                {
                    "id": "claude-test",
                    "name": "Claude Test",
                    "provider": "anthropic",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }
            ],
            "default_model": "claude-test",
            "fallback_model": "claude-test",
        }
        config_path = tmp_path / "anthropic_models.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)
        return config_path

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("backend.agents.base.llm_client.ChatAnthropic")
    def test_get_llm_anthropic(
        self, mock_chat_anthropic: MagicMock, anthropic_config: Path
    ) -> None:
        """测试获取 Anthropic LLM"""
        LLMClient.reset()
        mock_llm = MagicMock(spec=BaseChatModel)
        mock_chat_anthropic.return_value = mock_llm

        client = LLMClient(anthropic_config)
        llm = client.get_llm("claude-test")

        assert llm == mock_llm
        mock_chat_anthropic.assert_called_once()


class TestUnsupportedProvider:
    """测试不支持的提供商"""

    @pytest.fixture
    def unsupported_config(self, tmp_path: Path) -> Path:
        """创建不支持的提供商配置文件"""
        config = {
            "models": [
                {
                    "id": "unsupported-model",
                    "name": "Unsupported Model",
                    "provider": "unsupported",
                    "api_key_env": "UNSUPPORTED_API_KEY",
                }
            ],
            "default_model": "unsupported-model",
            "fallback_model": "unsupported-model",
        }
        config_path = tmp_path / "unsupported_models.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)
        return config_path

    @patch.dict(os.environ, {"UNSUPPORTED_API_KEY": "test-key"})
    def test_unsupported_provider(self, unsupported_config: Path) -> None:
        """测试不支持的提供商"""
        LLMClient.reset()
        client = LLMClient(unsupported_config)
        with pytest.raises(LLMClientError, match="不支持的提供商"):
            client.get_llm("unsupported-model")
