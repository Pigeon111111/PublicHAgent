"""LLM 客户端封装模块

提供统一的 LLM 客户端接口，支持 OpenAI 和 Anthropic 模型。
使用单例缓存机制避免重复初始化，支持错误处理和重试逻辑。
"""

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class ModelConfig(BaseModel):
    """模型配置"""

    id: str
    name: str
    provider: str
    base_url: str | None = None
    api_key_env: str
    max_tokens: int = 4096
    temperature: float = 0.7
    supports_streaming: bool = True
    supports_function_calling: bool = True


class ModelsConfig(BaseModel):
    """模型配置集合"""

    models: list[ModelConfig]
    default_model: str = "gpt-4o"
    fallback_model: str = "gpt-4o-mini"


class LLMClientError(Exception):
    """LLM 客户端错误"""

    pass


class LLMClient:
    """LLM 客户端封装类

    使用单例缓存机制，支持从 models.json 加载配置，
    提供统一的 LLM 客户端接口。
    """

    _instances: dict[str, BaseChatModel] = {}
    _config: ModelsConfig | None = None
    _config_path: Path | None = None
    _response_cache: Dict[str, Dict[str, Any]] = {}
    _cache_expiry: int = 24 * 60 * 60  # 24小时
    _max_cache_size: int = 1000  # 最大缓存记录数

    def __init__(self, config_path: str | Path | None = None):
        """初始化 LLM 客户端

        Args:
            config_path: 配置文件路径，默认为 backend/config/models.json
        """
        if config_path:
            self._config_path = Path(config_path)
        self._load_config()

    def _load_config(self) -> None:
        """加载模型配置"""
        if self._config is not None:
            return

        if self._config_path is None:
            self._config_path = Path(__file__).parent.parent.parent / "config" / "models.json"

        if not self._config_path.exists():
            raise LLMClientError(f"配置文件不存在: {self._config_path}")

        with open(self._config_path, encoding="utf-8") as f:
            config_data = json.load(f)

        self._config = ModelsConfig(**config_data)

    def _ensure_config(self) -> ModelsConfig:
        """确保配置已加载"""
        if self._config is None:
            self._load_config()
        assert self._config is not None
        return self._config

    def get_model_config(self, model_id: str) -> ModelConfig:
        """获取指定模型的配置

        Args:
            model_id: 模型 ID

        Returns:
            模型配置

        Raises:
            LLMClientError: 模型不存在
        """
        config = self._ensure_config()

        for model in config.models:
            if model.id == model_id:
                return model

        raise LLMClientError(f"模型不存在: {model_id}")

    def _create_llm(self, model_config: ModelConfig) -> BaseChatModel:
        """创建 LLM 实例

        Args:
            model_config: 模型配置

        Returns:
            LLM 实例

        Raises:
            LLMClientError: 不支持的提供商或 API Key 未配置
        """
        api_key = os.getenv(model_config.api_key_env)
        if not api_key:
            raise LLMClientError(f"API Key 未配置: {model_config.api_key_env}")

        provider = model_config.provider.lower()

        if provider == "openai":
            return ChatOpenAI(
                model=model_config.id,
                api_key=SecretStr(api_key),
                base_url=model_config.base_url,
                temperature=model_config.temperature,
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model_name=model_config.id,
                api_key=SecretStr(api_key),
                temperature=model_config.temperature,
                timeout=None,
                stop=None,
            )
        else:
            raise LLMClientError(f"不支持的提供商: {provider}")

    def get_llm(self, model_id: str | None = None) -> BaseChatModel:
        """获取 LLM 实例（单例缓存）

        Args:
            model_id: 模型 ID，默认使用 default_model

        Returns:
            LLM 实例
        """
        config = self._ensure_config()

        if model_id is None:
            model_id = config.default_model

        if model_id in self._instances:
            return self._instances[model_id]

        model_config = self.get_model_config(model_id)
        llm = self._create_llm(model_config)
        self._instances[model_id] = llm

        return llm

    def get_default_llm(self) -> BaseChatModel:
        """获取默认 LLM 实例

        Returns:
            默认 LLM 实例
        """
        return self.get_llm()

    def get_fallback_llm(self) -> BaseChatModel:
        """获取备用 LLM 实例

        Returns:
            备用 LLM 实例
        """
        config = self._ensure_config()
        return self.get_llm(config.fallback_model)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def invoke_with_retry(
        self, model_id: str | None, messages: list[Any]
    ) -> Any:
        """带重试的 LLM 调用

        Args:
            model_id: 模型 ID
            messages: 消息列表

        Returns:
            LLM 响应
        """
        # 使用默认模型 ID（如果未提供）
        config = self._ensure_config()
        if model_id is None:
            model_id = config.default_model
        
        # 尝试从缓存获取响应
        cached_response = self._get_from_cache(model_id, messages)
        if cached_response is not None:
            return cached_response
        
        # 缓存未命中，调用 LLM
        llm = self.get_llm(model_id)
        response = await llm.ainvoke(messages)
        
        # 将响应添加到缓存
        self._add_to_cache(model_id, messages, response)
        
        return response

    def _generate_cache_key(self, model_id: str, messages: List[Any]) -> str:
        """生成缓存键

        Args:
            model_id: 模型 ID
            messages: 消息列表

        Returns:
            缓存键
        """
        # 将消息转换为字符串
        messages_str = json.dumps(messages, sort_keys=True)
        # 组合模型 ID 和消息
        combined = f"{model_id}:{messages_str}"
        # 使用 MD5 生成缓存键
        return hashlib.md5(combined.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否有效

        Args:
            cache_entry: 缓存条目

        Returns:
            是否有效
        """
        timestamp = cache_entry.get('timestamp', 0)
        return time.time() - timestamp < self._cache_expiry

    def _get_from_cache(self, model_id: str, messages: List[Any]) -> Optional[Any]:
        """从缓存获取响应

        Args:
            model_id: 模型 ID
            messages: 消息列表

        Returns:
            缓存的响应，如果不存在或已过期则返回 None
        """
        cache_key = self._generate_cache_key(model_id, messages)
        if cache_key in self._response_cache:
            cache_entry = self._response_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                return cache_entry['response']
            else:
                # 清理过期缓存
                del self._response_cache[cache_key]
        return None

    def _add_to_cache(self, model_id: str, messages: List[Any], response: Any) -> None:
        """向缓存添加响应

        Args:
            model_id: 模型 ID
            messages: 消息列表
            response: LLM 响应
        """
        # 清理过期缓存
        self._clean_expired_cache()
        
        # 检查缓存大小
        if len(self._response_cache) >= self._max_cache_size:
            # 删除最旧的缓存
            oldest_key = min(
                self._response_cache.keys(),
                key=lambda k: self._response_cache[k].get('timestamp', 0)
            )
            del self._response_cache[oldest_key]
        
        # 添加新缓存
        cache_key = self._generate_cache_key(model_id, messages)
        self._response_cache[cache_key] = {
            'response': response,
            'timestamp': time.time()
        }

    def _clean_expired_cache(self) -> None:
        """清理过期缓存"""
        expired_keys = []
        for key, entry in self._response_cache.items():
            if not self._is_cache_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._response_cache[key]

    def clear_cache(self) -> None:
        """清除缓存"""
        self._instances.clear()
        self._response_cache.clear()

    @classmethod
    def reset(cls) -> None:
        """重置类级别的缓存和配置"""
        cls._instances.clear()
        cls._response_cache.clear()
        cls._config = None
        cls._config_path = None


def get_llm_client(config_path: str | Path | None = None) -> LLMClient:
    """获取 LLM 客户端实例

    Args:
        config_path: 配置文件路径

    Returns:
        LLM 客户端实例
    """
    return LLMClient(config_path)
