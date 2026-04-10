"""配置管理路由

提供获取和更新系统配置的接口。
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class AppConfig(BaseModel):
    """应用配置"""

    name: str = "PubHAgent"
    version: str = "0.1.0"
    debug: bool = False


class AgentConfig(BaseModel):
    """Agent 配置"""

    max_iterations: int = Field(default=10, ge=1, le=50)
    reflection_attempts: int = Field(default=3, ge=1, le=10)


class SandboxConfig(BaseModel):
    """沙箱配置"""

    enabled: bool = True
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    timeout: int = Field(default=60, ge=10, le=600)
    network_disabled: bool = True


class MemoryConfigResponse(BaseModel):
    """记忆配置响应"""

    provider: str = "mem0"
    vector_store: str = "chromadb"
    embedding_model: str = "text-embedding-3-small"
    short_term_limit: int = 10
    long_term_enabled: bool = True


class APIConfig(BaseModel):
    """API 配置"""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    websocket_path: str = "/ws"


class FullConfig(BaseModel):
    """完整配置"""

    app: AppConfig
    agent: AgentConfig
    sandbox: SandboxConfig
    memory: MemoryConfigResponse
    api: APIConfig


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""

    agent: AgentConfig | None = None
    sandbox: SandboxConfig | None = None


def _load_config() -> dict[str, Any]:
    """加载配置文件"""
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
            return dict(data) if isinstance(data, dict) else {}
    return {}


def _save_config(config: dict[str, Any]) -> None:
    """保存配置文件"""
    config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


@router.get("/config", response_model=FullConfig)
async def get_config() -> FullConfig:
    """获取完整配置

    Returns:
        完整配置
    """
    config_data = _load_config()

    return FullConfig(
        app=AppConfig(**config_data.get("app", {})),
        agent=AgentConfig(**config_data.get("agent", {})),
        sandbox=SandboxConfig(**config_data.get("sandbox", {})),
        memory=MemoryConfigResponse(**config_data.get("memory", {})),
        api=APIConfig(**config_data.get("api", {})),
    )


@router.get("/config/app", response_model=AppConfig)
async def get_app_config() -> AppConfig:
    """获取应用配置

    Returns:
        应用配置
    """
    config_data = _load_config()
    return AppConfig(**config_data.get("app", {}))


@router.get("/config/agent", response_model=AgentConfig)
async def get_agent_config() -> AgentConfig:
    """获取 Agent 配置

    Returns:
        Agent 配置
    """
    config_data = _load_config()
    return AgentConfig(**config_data.get("agent", {}))


@router.put("/config/agent", response_model=AgentConfig)
async def update_agent_config(config: AgentConfig) -> AgentConfig:
    """更新 Agent 配置

    Args:
        config: 新的 Agent 配置

    Returns:
        更新后的配置
    """
    full_config = _load_config()
    full_config["agent"] = config.model_dump()
    _save_config(full_config)
    return config


@router.get("/config/sandbox", response_model=SandboxConfig)
async def get_sandbox_config() -> SandboxConfig:
    """获取沙箱配置

    Returns:
        沙箱配置
    """
    config_data = _load_config()
    return SandboxConfig(**config_data.get("sandbox", {}))


@router.put("/config/sandbox", response_model=SandboxConfig)
async def update_sandbox_config(config: SandboxConfig) -> SandboxConfig:
    """更新沙箱配置

    Args:
        config: 新的沙箱配置

    Returns:
        更新后的配置
    """
    full_config = _load_config()
    full_config["sandbox"] = config.model_dump()
    _save_config(full_config)
    return config


@router.get("/config/memory", response_model=MemoryConfigResponse)
async def get_memory_config() -> MemoryConfigResponse:
    """获取记忆配置

    Returns:
        记忆配置
    """
    config_data = _load_config()
    return MemoryConfigResponse(**config_data.get("memory", {}))


@router.get("/config/api", response_model=APIConfig)
async def get_api_config() -> APIConfig:
    """获取 API 配置

    Returns:
        API 配置
    """
    config_data = _load_config()
    return APIConfig(**config_data.get("api", {}))


@router.patch("/config", response_model=FullConfig)
async def update_config(update: ConfigUpdateRequest) -> FullConfig:
    """部分更新配置

    Args:
        update: 配置更新请求

    Returns:
        更新后的完整配置
    """
    full_config = _load_config()

    if update.agent is not None:
        full_config["agent"] = update.agent.model_dump()

    if update.sandbox is not None:
        full_config["sandbox"] = update.sandbox.model_dump()

    _save_config(full_config)

    return await get_config()
