"""LLM 客户端封装模块

提供统一的 LLM 客户端接口，支持 OpenAI 和 Anthropic 模型。
使用单例缓存机制，支持错误处理和重试逻辑。
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.models.user_config import CustomModelConfig
from backend.storage.user_config_storage import get_user_config_storage

T = TypeVar("T", bound=BaseModel)


def _message_content_to_text(content: Any) -> str:
    """把 LangChain 消息内容统一转为文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content") or item
                parts.append(str(value))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


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
    _response_cache: dict[str, dict[str, Any]] = {}
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

    def _create_llm(
        self,
        model_config: ModelConfig,
        user_id: str = "default",
    ) -> BaseChatModel:
        """创建 LLM 实例

        Args:
            model_config: 模型配置
            user_id: 用户 ID，用于获取用户配置的 API Key

        Returns:
            LLM 实例

        Raises:
            LLMClientError: 不支持的提供商或 API Key 未配置
        """
        storage = get_user_config_storage()
        user_config = storage.get(user_id)

        api_key = None
        provider = model_config.provider.lower()

        if user_config:
            if provider == "openai" and user_config.api_keys.openai:
                api_key = user_config.api_keys.openai
            elif provider == "anthropic" and user_config.api_keys.anthropic:
                api_key = user_config.api_keys.anthropic
            elif provider == "deepseek" and user_config.api_keys.deepseek:
                api_key = user_config.api_keys.deepseek
            elif provider == "longcat" and user_config.api_keys.longcat:
                api_key = user_config.api_keys.longcat

        if not api_key:
            api_key = os.getenv(model_config.api_key_env)

        if not api_key:
            raise LLMClientError(f"API Key 未配置: {model_config.api_key_env}")

        if provider == "openai":
            return ChatOpenAI(
                model=model_config.id,
                api_key=SecretStr(api_key),
                base_url=model_config.base_url,
                temperature=model_config.temperature,
                timeout=30,
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model_name=model_config.id,
                api_key=SecretStr(api_key),
                temperature=model_config.temperature,
                timeout=30,
                stop=None,
            )
        elif provider in ("deepseek", "longcat", "custom"):
            return ChatOpenAI(
                model=model_config.id,
                api_key=SecretStr(api_key),
                base_url=model_config.base_url,
                temperature=model_config.temperature,
                timeout=30,
            )
        else:
            raise LLMClientError(f"不支持的提供商: {provider}")

    def get_llm(
        self,
        model_id: str | None = None,
        user_id: str = "default",
    ) -> BaseChatModel:
        """获取 LLM 实例（单例缓存）

        Args:
            model_id: 模型 ID，默认使用 default_model
            user_id: 用户 ID，用于获取用户配置的 API Key

        Returns:
            LLM 实例
        """
        config = self._ensure_config()

        if model_id is None:
            model_id = config.default_model

        cache_key = f"{user_id}:{model_id}"
        if cache_key in self._instances:
            return self._instances[cache_key]

        model_config = self.get_model_config(model_id)
        llm = self._create_llm(model_config, user_id)
        self._instances[cache_key] = llm

        return llm

    def get_default_llm(self, user_id: str = "default") -> BaseChatModel:
        """获取默认 LLM 实例

        Args:
            user_id: 用户 ID

        Returns:
            默认 LLM 实例
        """
        return self.get_llm(user_id=user_id)

    def get_fallback_llm(self, user_id: str = "default") -> BaseChatModel:
        """获取备用 LLM 实例

        Args:
            user_id: 用户 ID

        Returns:
            备用 LLM 实例
        """
        config = self._ensure_config()
        return self.get_llm(config.fallback_model, user_id)

    def get_llm_from_custom_config(
        self,
        custom_config: CustomModelConfig,
        cache_key: str | None = None,
    ) -> BaseChatModel:
        """从自定义模型配置创建 LLM 实例

        Args:
            custom_config: 自定义模型配置
            cache_key: 缓存键，用于单例缓存

        Returns:
            LLM 实例

        Raises:
            LLMClientError: API Key 未配置
        """
        if cache_key and cache_key in self._instances:
            return self._instances[cache_key]

        if not custom_config.api_key:
            raise LLMClientError(f"自定义模型 {custom_config.name} 未配置 API Key")

        llm = ChatOpenAI(
            model=custom_config.model_id,
            api_key=SecretStr(custom_config.api_key),
            base_url=custom_config.base_url,
            temperature=custom_config.temperature,
            model_kwargs={"max_tokens": custom_config.max_tokens},
            timeout=30,
        )

        if cache_key:
            self._instances[cache_key] = llm

        return llm

    def get_llm_for_user(
        self,
        user_id: str,
        model_type: str = "planner",
    ) -> BaseChatModel:
        """获取用户的 LLM 实例

        根据用户配置的模型选择，返回对应的 LLM 实例。
        优先使用用户自定义模型，其次使用系统预设模型。

        Args:
            user_id: 用户 ID
            model_type: 模型类型 (planner/executor)

        Returns:
            LLM 实例

        Raises:
            LLMClientError: 模型配置错误
        """
        storage = get_user_config_storage()
        user_config = storage.get(user_id)

        if user_config is None:
            return self.get_default_llm(user_id)

        model_name = (
            user_config.preferences.planner_model
            if model_type == "planner"
            else user_config.preferences.executor_model
        )

        if model_name in user_config.custom_models:
            custom_config = user_config.custom_models[model_name]
            cache_key = f"user:{user_id}:{model_name}"
            return self.get_llm_from_custom_config(custom_config, cache_key)

        try:
            return self.get_llm(model_name, user_id)
        except LLMClientError:
            return self.get_default_llm(user_id)

    def get_planner_llm(self, user_id: str = "default") -> BaseChatModel:
        """获取 Planner 使用的 LLM 实例

        Args:
            user_id: 用户 ID

        Returns:
            LLM 实例
        """
        return self.get_llm_for_user(user_id, "planner")

    def get_executor_llm(self, user_id: str = "default") -> BaseChatModel:
        """获取 Executor 使用的 LLM 实例

        Args:
            user_id: 用户 ID

        Returns:
            LLM 实例
        """
        return self.get_llm_for_user(user_id, "executor")

    async def invoke_structured(
        self,
        llm: BaseChatModel,
        messages: list[BaseMessage],
        output_model: type[T],
    ) -> T:
        """调用 LLM 并返回结构化输出

        优先使用 with_structured_output，失败时回退到 JSON 解析。

        Args:
            llm: LLM 实例
            messages: 消息列表
            output_model: 输出模型类型

        Returns:
            结构化输出
        """
        try:
            structured_llm = llm.with_structured_output(output_model)
            result = await structured_llm.ainvoke(messages)
            if isinstance(result, output_model):
                return result
            raise ValueError(f"Unexpected result type: {type(result)}")
        except Exception:
            # 回退到普通调用 + JSON 解析
            response = await llm.ainvoke(messages)
            return self._parse_structured_output(response, output_model)

    def _parse_structured_output(
        self,
        response: BaseMessage,
        output_model: type[T],
    ) -> T:
        """从 LLM 响应中解析结构化输出

        Args:
            response: LLM 响应
            output_model: 输出模型类型

        Returns:
            结构化输出

        Raises:
            ValueError: 解析失败
        """
        content = _message_content_to_text(response.content if hasattr(response, "content") else response)

        # 尝试从响应中提取 JSON
        json_patterns = [
            r"```json\s*([\s\S]*?)\s*```",  # ```json ... ```
            r"```\s*([\s\S]*?)\s*```",  # ``` ... ```
            r"\{[\s\S]*\}",  # 直接的 JSON 对象
        ]

        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    json_str = match.group(1) if "```" in pattern else match.group(0)
                    data = json.loads(json_str)
                    return output_model.model_validate(data)
                except (json.JSONDecodeError, ValueError):
                    continue

        raise ValueError(f"无法从响应中解析 {output_model.__name__}: {content[:200]}")

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

    def _generate_cache_key(self, model_id: str, messages: list[Any]) -> str:
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

    def _is_cache_valid(self, cache_entry: dict[str, Any]) -> bool:
        """检查缓存是否有效

        Args:
            cache_entry: 缓存条目

        Returns:
            是否有效
        """
        timestamp: float = cache_entry.get('timestamp', 0)
        return time.time() - timestamp < self._cache_expiry

    def _get_from_cache(self, model_id: str, messages: list[Any]) -> Any | None:
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

    def _add_to_cache(self, model_id: str, messages: list[Any], response: Any) -> None:
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


async def invoke_structured_output(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    output_model: type[T],
) -> T:
    """调用 LLM 并返回结构化输出

    优先使用 with_structured_output，失败时回退到普通调用 + JSON 解析。

    Args:
        llm: LLM 实例
        messages: 消息列表
        output_model: 输出模型类型

    Returns:
        结构化输出
    """
    try:
        structured_llm = llm.with_structured_output(output_model)
        result = await structured_llm.ainvoke(messages)
        if isinstance(result, output_model):
            return result
        raise ValueError(f"Unexpected result type: {type(result)}")
    except Exception:
        # 回退到普通调用 + JSON 解析
        # 获取 schema 的简化版本
        schema = output_model.model_json_schema()
        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})

        # 构建简化的字段说明
        field_descriptions = []
        for field_name in required_fields:
            field_info = properties.get(field_name, {})
            field_type = field_info.get("type", "any")
            field_desc = field_info.get("description", "")
            field_descriptions.append(f"  - {field_name} ({field_type}): {field_desc}")

        json_instruction = f"""

请以 JSON 格式返回结果，包含以下字段:
{chr(10).join(field_descriptions)}

重要提示：
1. 只返回实际的 JSON 对象，不要返回 schema 定义
2. 不要包含 ```json 或 ``` 标记
3. 确保所有必填字段都有值

示例格式:
{{"{required_fields[0] if required_fields else 'field'}': "value"}}"""

        # 修改最后一条消息
        modified_messages = list(messages)
        if modified_messages:
            last_msg = modified_messages[-1]
            if hasattr(last_msg, "content"):
                new_content = _message_content_to_text(last_msg.content) + json_instruction
                modified_messages[-1] = HumanMessage(content=new_content)

        response = await llm.ainvoke(modified_messages)
        return _parse_structured_output(response, output_model)


def _parse_structured_output(
    response: BaseMessage,
    output_model: type[T],
) -> T:
    """从 LLM 响应中解析结构化输出

    Args:
        response: LLM 响应
        output_model: 输出模型类型

    Returns:
        结构化输出

    Raises:
        ValueError: 解析失败
    """
    content = _message_content_to_text(response.content if hasattr(response, "content") else response)

    def clean_null_values(data: Any) -> Any:
        """清理 null 值，让 Pydantic 使用默认值"""
        if not isinstance(data, dict):
            return data
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = clean_null_values(value)
            elif isinstance(value, list):
                result[key] = [clean_null_values(item) if isinstance(item, dict) else item for item in value]
            elif value is not None:
                result[key] = value
        return result

    # 方法1: 尝试直接解析整个内容
    try:
        data = json.loads(content.strip())
        if isinstance(data, dict) and "properties" not in data:
            data = clean_null_values(data)
            return output_model.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        pass

    # 方法2: 从代码块中提取 JSON
    code_block_patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]
    for pattern in code_block_patterns:
        match = re.search(pattern, content)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if isinstance(data, dict) and "properties" not in data:
                    data = clean_null_values(data)
                    return output_model.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                continue

    # 方法3: 查找第一个完整的 JSON 对象
    start_idx = content.find("{")
    if start_idx != -1:
        depth = 0
        end_idx = start_idx
        for i, char in enumerate(content[start_idx:], start_idx):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        if end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and "properties" not in data:
                    data = clean_null_values(data)
                    return output_model.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass

    raise ValueError(f"无法从响应中解析 {output_model.__name__}: {content[:500]}")
