"""用户配置 API 路由

提供用户配置管理功能，包括 API Key 管理、自定义模型管理、偏好设置等。
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.models.user_config import (
    APIKeyUpdate,
    CustomModelConfig,
    CustomModelCreate,
    CustomModelUpdate,
    ModelSelection,
    UserConfig,
    UserConfigUpdate,
)
from backend.storage.user_config_storage import get_user_config_storage

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/config")
async def get_user_config(user_id: str = "default") -> dict[str, Any]:
    """获取用户配置

    Args:
        user_id: 用户 ID

    Returns:
        用户配置
    """
    try:
        storage = get_user_config_storage()
        config = storage.get(user_id)

        if config is None:
            return {
                "success": True,
                "config": None,
                "message": "用户配置不存在",
            }

        custom_models_info = {}
        for name, model_config in config.custom_models.items():
            custom_models_info[name] = {
                "name": model_config.name,
                "model_id": model_config.model_id,
                "base_url": model_config.base_url,
                "has_api_key": model_config.api_key is not None,
                "max_tokens": model_config.max_tokens,
                "temperature": model_config.temperature,
                "supports_streaming": model_config.supports_streaming,
                "supports_function_calling": model_config.supports_function_calling,
            }

        return {
            "success": True,
            "config": {
                "user_id": config.user_id,
                "custom_models": custom_models_info,
                "enabled_skills": config.enabled_skills,
                "preferences": config.preferences.model_dump(),
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户配置失败: {e}") from e


@router.put("/config")
async def update_user_config(
    request: UserConfigUpdate,
    user_id: str = "default",
) -> dict[str, Any]:
    """更新用户配置

    Args:
        request: 更新请求
        user_id: 用户 ID

    Returns:
        更新结果
    """
    try:
        storage = get_user_config_storage()

        updates = request.model_dump(exclude_unset=True)
        config = storage.update(user_id, updates)

        if config is None:
            config = UserConfig(user_id=user_id)
            if request.enabled_skills is not None:
                config.enabled_skills = request.enabled_skills
            if request.preferences is not None:
                config.preferences = request.preferences
            storage.save(config)

        return {
            "success": True,
            "message": "用户配置更新成功",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新用户配置失败: {e}") from e


# ============ API Key 管理 ============

@router.put("/api-key")
async def set_api_key(request: APIKeyUpdate) -> dict[str, Any]:
    """设置 API Key

    Args:
        request: API Key 更新请求

    Returns:
        设置结果
    """
    try:
        storage = get_user_config_storage()
        storage.set_api_key("default", request.provider, request.api_key)

        return {
            "success": True,
            "message": f"API Key 设置成功: {request.provider}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置 API Key 失败: {e}") from e


@router.get("/api-key/{provider}")
async def get_api_key(provider: str) -> dict[str, Any]:
    """获取 API Key（脱敏显示）

    Args:
        provider: 提供商名称

    Returns:
        API Key 信息
    """
    try:
        storage = get_user_config_storage()
        api_key = storage.get_api_key("default", provider)

        if api_key is None:
            return {
                "success": True,
                "has_key": False,
                "masked_key": None,
            }

        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"

        return {
            "success": True,
            "has_key": True,
            "masked_key": masked_key,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 API Key 失败: {e}") from e


@router.delete("/api-key/{provider}")
async def delete_api_key(provider: str) -> dict[str, Any]:
    """删除 API Key

    Args:
        provider: 提供商名称

    Returns:
        删除结果
    """
    try:
        storage = get_user_config_storage()
        storage.set_api_key("default", provider, "")

        return {
            "success": True,
            "message": f"API Key 删除成功: {provider}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 API Key 失败: {e}") from e


# ============ 自定义模型管理 ============

@router.get("/custom-models")
async def list_custom_models() -> dict[str, Any]:
    """列出所有自定义模型

    Returns:
        自定义模型列表
    """
    try:
        storage = get_user_config_storage()
        models = storage.list_custom_models("default")

        models_info = {}
        for name, config in models.items():
            models_info[name] = {
                "name": config.name,
                "model_id": config.model_id,
                "base_url": config.base_url,
                "has_api_key": config.api_key is not None,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "supports_streaming": config.supports_streaming,
                "supports_function_calling": config.supports_function_calling,
            }

        return {
            "success": True,
            "models": models_info,
            "total": len(models_info),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取自定义模型列表失败: {e}") from e


@router.post("/custom-models")
async def create_custom_model(request: CustomModelCreate) -> dict[str, Any]:
    """创建自定义模型

    Args:
        request: 创建请求

    Returns:
        创建结果
    """
    try:
        storage = get_user_config_storage()

        existing = storage.get_custom_model("default", request.model_name)
        if existing:
            raise HTTPException(status_code=400, detail=f"模型已存在: {request.model_name}")

        config = CustomModelConfig(
            name=request.name,
            model_id=request.model_id,
            base_url=request.base_url,
            api_key=request.api_key,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            supports_streaming=request.supports_streaming,
            supports_function_calling=request.supports_function_calling,
        )

        storage.add_custom_model("default", request.model_name, config)

        return {
            "success": True,
            "message": f"自定义模型创建成功: {request.model_name}",
            "model": {
                "model_name": request.model_name,
                "name": config.name,
                "model_id": config.model_id,
                "base_url": config.base_url,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建自定义模型失败: {e}") from e


@router.get("/custom-models/{model_name}")
async def get_custom_model(model_name: str) -> dict[str, Any]:
    """获取自定义模型详情

    Args:
        model_name: 模型名称

    Returns:
        模型详情
    """
    try:
        storage = get_user_config_storage()
        config = storage.get_custom_model("default", model_name)

        if config is None:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_name}")

        return {
            "success": True,
            "model": {
                "name": config.name,
                "model_id": config.model_id,
                "base_url": config.base_url,
                "has_api_key": config.api_key is not None,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "supports_streaming": config.supports_streaming,
                "supports_function_calling": config.supports_function_calling,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取自定义模型失败: {e}") from e


@router.put("/custom-models/{model_name}")
async def update_custom_model(
    model_name: str,
    request: CustomModelUpdate,
) -> dict[str, Any]:
    """更新自定义模型

    Args:
        model_name: 模型名称
        request: 更新请求

    Returns:
        更新结果
    """
    try:
        storage = get_user_config_storage()

        updates = request.model_dump(exclude_unset=True)
        config = storage.update_custom_model("default", model_name, updates)

        if config is None:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_name}")

        return {
            "success": True,
            "message": f"自定义模型更新成功: {model_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新自定义模型失败: {e}") from e


@router.delete("/custom-models/{model_name}")
async def delete_custom_model(model_name: str) -> dict[str, Any]:
    """删除自定义模型

    Args:
        model_name: 模型名称

    Returns:
        删除结果
    """
    try:
        storage = get_user_config_storage()
        success = storage.delete_custom_model("default", model_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_name}")

        return {
            "success": True,
            "message": f"自定义模型删除成功: {model_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除自定义模型失败: {e}") from e


# ============ 模型选择 ============

@router.put("/model-selection")
async def set_model_selection(request: ModelSelection) -> dict[str, Any]:
    """设置模型选择

    Args:
        request: 模型选择请求

    Returns:
        设置结果
    """
    try:
        storage = get_user_config_storage()
        storage.set_model_selection("default", request.model_type, request.model_name)

        return {
            "success": True,
            "message": f"模型选择设置成功: {request.model_type} -> {request.model_name}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置模型选择失败: {e}") from e


@router.get("/model-selection")
async def get_model_selection() -> dict[str, Any]:
    """获取当前模型选择

    Returns:
        模型选择信息
    """
    try:
        storage = get_user_config_storage()
        config = storage.get("default")

        if config is None:
            return {
                "success": True,
                "planner_model": "gpt-4o",
                "executor_model": "gpt-4o-mini",
            }

        return {
            "success": True,
            "planner_model": config.preferences.planner_model,
            "executor_model": config.preferences.executor_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型选择失败: {e}") from e


# ============ 可用模型列表 ============

@router.get("/available-models")
async def get_available_models() -> dict[str, Any]:
    """获取所有可用模型列表

    只返回已配置 API Key 的模型。

    Returns:
        可用模型列表
    """
    try:
        storage = get_user_config_storage()
        user_config = storage.get("default")

        models: list[dict[str, Any]] = []

        # 检查用户配置的 API Keys
        has_openai_key = False
        has_anthropic_key = False
        has_deepseek_key = False
        has_longcat_key = False

        if user_config:
            has_openai_key = bool(user_config.api_keys.openai)
            has_anthropic_key = bool(user_config.api_keys.anthropic)
            has_deepseek_key = bool(user_config.api_keys.deepseek)
            has_longcat_key = bool(user_config.api_keys.longcat)

        # 预设模型 - 只返回已配置 API Key 的
        if has_openai_key:
            models.extend([
                {"name": "GPT-4o", "model_id": "gpt-4o", "provider": "openai", "type": "preset"},
                {"name": "GPT-4o Mini", "model_id": "gpt-4o-mini", "provider": "openai", "type": "preset"},
                {"name": "GPT-4 Turbo", "model_id": "gpt-4-turbo", "provider": "openai", "type": "preset"},
                {"name": "GPT-3.5 Turbo", "model_id": "gpt-3.5-turbo", "provider": "openai", "type": "preset"},
            ])

        if has_anthropic_key:
            models.extend([
                {"name": "Claude 3.5 Sonnet", "model_id": "claude-3-5-sonnet-20241022", "provider": "anthropic", "type": "preset"},
                {"name": "Claude 3.5 Haiku", "model_id": "claude-3-5-haiku-20241022", "provider": "anthropic", "type": "preset"},
            ])

        if has_deepseek_key:
            models.extend([
                {"name": "DeepSeek Chat", "model_id": "deepseek-chat", "provider": "deepseek", "type": "preset"},
                {"name": "DeepSeek Coder", "model_id": "deepseek-coder", "provider": "deepseek", "type": "preset"},
            ])

        if has_longcat_key:
            models.append({"name": "LongCat Chat", "model_id": "longcat-chat", "provider": "longcat", "type": "preset"})

        # 用户自定义模型 - 只返回已配置 API Key 的
        if user_config and user_config.custom_models:
            for model_name, config in user_config.custom_models.items():
                if config.api_key:
                    models.append({
                        "name": config.name,
                        "model_id": config.model_id,
                        "model_name": model_name,
                        "provider": "custom",
                        "type": "custom",
                        "base_url": config.base_url,
                        "has_api_key": True,
                    })

        return {
            "success": True,
            "models": models,
            "total": len(models),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用模型失败: {e}") from e


# ============ Skills 管理 ============

@router.get("/enabled-skills")
async def get_enabled_skills() -> dict[str, Any]:
    """获取启用的 Skills

    Returns:
        启用的 Skills 列表
    """
    try:
        storage = get_user_config_storage()
        config = storage.get("default")

        enabled_skills = config.enabled_skills if config else []

        return {
            "success": True,
            "enabled_skills": enabled_skills,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取启用的 Skills 失败: {e}") from e


@router.put("/enabled-skills")
async def set_enabled_skills(skills: list[str]) -> dict[str, Any]:
    """设置启用的 Skills

    Args:
        skills: Skills 列表

    Returns:
        设置结果
    """
    try:
        storage = get_user_config_storage()
        storage.update("default", {"enabled_skills": skills})

        return {
            "success": True,
            "message": "启用的 Skills 设置成功",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置启用的 Skills 失败: {e}") from e
