"""用户配置模型

定义用户配置数据结构，支持 API Key 隔离存储和自定义模型配置。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CustomModelConfig(BaseModel):
    """自定义模型配置"""

    name: str = Field(description="模型显示名称")
    model_id: str = Field(description="模型 ID，用于 API 调用")
    base_url: str = Field(description="API Base URL")
    api_key: str | None = Field(default=None, description="API Key")
    max_tokens: int = Field(default=4096, description="最大 Token 数")
    temperature: float = Field(default=0.7, description="温度参数")
    supports_streaming: bool = Field(default=True, description="是否支持流式输出")
    supports_function_calling: bool = Field(default=True, description="是否支持函数调用")


class ProviderConfig(BaseModel):
    """提供商配置"""

    api_key: str | None = None
    base_url: str | None = None
    models: list[str] = Field(default_factory=list)


class UserAPIKeys(BaseModel):
    """用户 API Keys"""

    openai: str | None = None
    anthropic: str | None = None
    deepseek: str | None = None
    longcat: str | None = None
    custom: str | None = None


class UserPreferences(BaseModel):
    """用户偏好设置"""

    default_model: str = "gpt-4o"
    default_provider: str = "openai"
    planner_model: str = "gpt-4o"
    executor_model: str = "gpt-4o-mini"
    language: str = "zh-CN"
    theme: str = "light"
    enable_cache: bool = True
    max_iterations: int = 10
    timeout: int = 60


class UserConfig(BaseModel):
    """用户配置"""

    user_id: str = Field(description="用户 ID")
    api_keys: UserAPIKeys = Field(default_factory=UserAPIKeys, description="加密的 API Keys")
    custom_models: dict[str, CustomModelConfig] = Field(
        default_factory=dict, description="自定义模型配置"
    )
    enabled_skills: list[str] = Field(default_factory=list, description="启用的 Skills")
    preferences: UserPreferences = Field(default_factory=UserPreferences, description="用户偏好")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    def touch(self) -> None:
        """更新修改时间"""
        self.updated_at = datetime.now()


class UserConfigCreate(BaseModel):
    """创建用户配置请求"""

    user_id: str
    api_keys: UserAPIKeys | None = None
    custom_models: dict[str, CustomModelConfig] | None = None
    enabled_skills: list[str] | None = None
    preferences: UserPreferences | None = None


class UserConfigUpdate(BaseModel):
    """更新用户配置请求"""

    api_keys: UserAPIKeys | None = None
    custom_models: dict[str, CustomModelConfig] | None = None
    enabled_skills: list[str] | None = None
    preferences: UserPreferences | None = None


class APIKeyUpdate(BaseModel):
    """更新 API Key 请求"""

    provider: str = Field(description="提供商名称")
    api_key: str = Field(description="API Key（明文，将被加密存储）")


class CustomModelCreate(BaseModel):
    """创建自定义模型请求"""

    model_name: str = Field(description="模型唯一标识名称")
    name: str = Field(description="模型显示名称")
    model_id: str = Field(description="模型 ID，用于 API 调用")
    base_url: str = Field(description="API Base URL")
    api_key: str | None = Field(default=None, description="API Key")
    max_tokens: int = Field(default=4096, description="最大 Token 数")
    temperature: float = Field(default=0.7, description="温度参数")
    supports_streaming: bool = Field(default=True, description="是否支持流式输出")
    supports_function_calling: bool = Field(default=True, description="是否支持函数调用")


class CustomModelUpdate(BaseModel):
    """更新自定义模型请求"""

    name: str | None = None
    model_id: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    supports_streaming: bool | None = None
    supports_function_calling: bool | None = None


class ModelSelection(BaseModel):
    """模型选择请求"""

    model_type: str = Field(description="模型类型: planner/executor")
    model_name: str = Field(description="模型名称")
