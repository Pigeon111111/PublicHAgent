"""Skill 管理 API 路由

提供 Skill 的 CRUD 操作和启用/禁用功能。
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.tools.skills.loader import SkillLoader
from backend.tools.skills.models import (
    Skill,
    SkillCapability,
    SkillMetadata,
    SkillParameter,
)
from backend.tools.skills.registry import get_skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills() -> dict[str, Any]:
    """列出所有 Skill

    Returns:
        Skill 列表
    """
    try:
        registry = get_skill_registry()
        skills = registry.list_skills()

        skill_list = []
        for skill_name in skills:
            skill = registry.get(skill_name)
            skill_list.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.metadata.category,
                "version": skill.metadata.version,
                "enabled": registry.is_enabled(skill_name),
                "capability": skill.capability.capability,
            })

        return {
            "success": True,
            "skills": skill_list,
            "total": len(skill_list),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Skill 列表失败: {e}") from e


@router.get("/{skill_name}")
async def get_skill(skill_name: str) -> dict[str, Any]:
    """获取 Skill 详情

    Args:
        skill_name: Skill 名称

    Returns:
        Skill 详情
    """
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        skill = registry.get(skill_name)
        return {
            "success": True,
            "skill": {
                "name": skill.name,
                "description": skill.description,
                "version": skill.metadata.version,
                "author": skill.metadata.author,
                "category": skill.metadata.category,
                "tags": skill.metadata.tags,
                "capability": {
                    "capability": skill.capability.capability,
                    "limitations": skill.capability.limitations,
                    "applicable_scenarios": skill.capability.applicable_scenarios,
                },
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in skill.parameters
                ],
                "notes": skill.notes,
                "enabled": registry.is_enabled(skill_name),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Skill 详情失败: {e}") from e


class CreateSkillRequest(BaseModel):
    """创建 Skill 请求"""

    name: str
    description: str
    category: str = "general"
    capability: str
    limitations: list[str] = []
    applicable_scenarios: list[str] = []
    parameters: list[dict[str, Any]] = []
    prompt_template: str = ""
    notes: list[str] = []


@router.post("")
async def create_skill(request: CreateSkillRequest) -> dict[str, Any]:
    """创建新 Skill

    Args:
        request: 创建请求

    Returns:
        创建结果
    """
    try:
        registry = get_skill_registry()

        if registry.has(request.name):
            raise HTTPException(status_code=400, detail=f"Skill 已存在: {request.name}")

        parameters = [
            SkillParameter(
                name=p.get("name", ""),
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
            )
            for p in request.parameters
        ]

        skill = Skill(
            metadata=SkillMetadata(
                name=request.name,
                description=request.description,
                category=request.category,
            ),
            capability=SkillCapability(
                capability=request.capability,
                limitations=request.limitations,
                applicable_scenarios=request.applicable_scenarios,
            ),
            parameters=parameters,
            prompt_template=request.prompt_template,
            notes=request.notes,
        )

        skill_dir = Path(__file__).parent.parent.parent / "tools" / "skills" / request.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skill_dir / "SKILL.md"
        skill_content = _generate_skill_markdown(skill)
        skill_file.write_text(skill_content, encoding="utf-8")

        loader = SkillLoader()
        loaded_skill = loader.load_skill(request.name, use_cache=False)
        if registry.has(loaded_skill.name):
            registry.unregister_skill(loaded_skill.name)
        registry.register_skill(loaded_skill)

        return {
            "success": True,
            "message": f"Skill 创建成功: {request.name}",
            "skill": {
                "name": loaded_skill.name,
                "description": loaded_skill.description,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 Skill 失败: {e}") from e


class UpdateSkillRequest(BaseModel):
    """更新 Skill 请求"""

    description: str | None = None
    capability: str | None = None
    limitations: list[str] | None = None
    applicable_scenarios: list[str] | None = None
    parameters: list[dict[str, Any]] | None = None
    prompt_template: str | None = None
    notes: list[str] | None = None


@router.put("/{skill_name}")
async def update_skill(skill_name: str, request: UpdateSkillRequest) -> dict[str, Any]:
    """更新 Skill

    Args:
        skill_name: Skill 名称
        request: 更新请求

    Returns:
        更新结果
    """
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        loader = SkillLoader()
        skill = loader.load_skill(skill_name, use_cache=False)

        if request.description is not None:
            skill.metadata.description = request.description
        if request.capability is not None:
            skill.capability.capability = request.capability
        if request.limitations is not None:
            skill.capability.limitations = request.limitations
        if request.applicable_scenarios is not None:
            skill.capability.applicable_scenarios = request.applicable_scenarios
        if request.parameters is not None:
            skill.parameters = [
                SkillParameter(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    default=p.get("default"),
                )
                for p in request.parameters
            ]
        if request.prompt_template is not None:
            skill.prompt_template = request.prompt_template
        if request.notes is not None:
            skill.notes = request.notes

        skill_dir = Path(__file__).parent.parent.parent / "tools" / "skills" / skill_name
        skill_file = skill_dir / "SKILL.md"
        skill_content = _generate_skill_markdown(skill)
        skill_file.write_text(skill_content, encoding="utf-8")

        loaded_skill = loader.reload_skill(skill_name)
        if registry.has(skill_name):
            registry.unregister_skill(skill_name)
        registry.register_skill(loaded_skill)

        return {
            "success": True,
            "message": f"Skill 更新成功: {skill_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新 Skill 失败: {e}") from e


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str) -> dict[str, Any]:
    """删除 Skill

    Args:
        skill_name: Skill 名称

    Returns:
        删除结果
    """
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        skill_dir = Path(__file__).parent.parent.parent / "tools" / "skills" / skill_name
        if not skill_dir.exists():
            raise HTTPException(status_code=404, detail=f"Skill 目录不存在: {skill_name}")

        import shutil
        shutil.rmtree(skill_dir)

        if registry.has(skill_name):
            registry.unregister_skill(skill_name)

        return {
            "success": True,
            "message": f"Skill 删除成功: {skill_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 Skill 失败: {e}") from e


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str) -> dict[str, Any]:
    """启用 Skill

    Args:
        skill_name: Skill 名称

    Returns:
        启用结果
    """
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        registry.enable(skill_name)

        return {
            "success": True,
            "message": f"Skill 已启用: {skill_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启用 Skill 失败: {e}") from e


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str) -> dict[str, Any]:
    """禁用 Skill

    Args:
        skill_name: Skill 名称

    Returns:
        禁用结果
    """
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        registry.disable(skill_name)

        return {
            "success": True,
            "message": f"Skill 已禁用: {skill_name}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"禁用 Skill 失败: {e}") from e


@router.get("/capabilities/all")
async def get_all_capabilities() -> dict[str, Any]:
    """获取所有 Skill 的能力描述

    Returns:
        能力描述字典
    """
    try:
        registry = get_skill_registry()
        skills = registry.list_skills()

        capabilities = {}
        for skill_name in skills:
            skill = registry.get(skill_name)
            capabilities[skill_name] = {
                "name": skill.name,
                "description": skill.description,
                "capability": skill.capability.capability,
                "limitations": skill.capability.limitations,
                "applicable_scenarios": skill.capability.applicable_scenarios,
            }

        return {
            "success": True,
            "capabilities": capabilities,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取能力描述失败: {e}") from e


def _generate_skill_markdown(skill: Skill) -> str:
    """生成 Skill Markdown 文件内容

    Args:
        skill: Skill 对象

    Returns:
        Markdown 内容
    """
    lines = [
        "---",
        f'name: {skill.metadata.name}',
        f'version: {skill.metadata.version}',
        f'description: {skill.metadata.description}',
        f'author: {skill.metadata.author}',
        "tags:",
    ]

    for tag in skill.metadata.tags:
        lines.append(f"  - {tag}")

    lines.append(f"category: {skill.metadata.category}")
    lines.append(f'min_python_version: "{skill.metadata.min_python_version}"')
    lines.append("dependencies:")

    for dep in skill.metadata.dependencies:
        lines.append(f"  - {dep}")

    lines.extend([
        "---",
        "",
        f"# {skill.metadata.name}",
        "",
        "## 能力描述",
        "",
        f"**能力范围**：{skill.capability.capability}",
        "",
    ])

    if skill.capability.limitations:
        lines.append("**限制条件**：")
        for limit in skill.capability.limitations:
            lines.append(f"- {limit}")
        lines.append("")

    if skill.capability.applicable_scenarios:
        lines.append("**适用场景**：")
        for scenario in skill.capability.applicable_scenarios:
            lines.append(f"- {scenario}")
        lines.append("")

    if skill.parameters:
        lines.append("## 参数")
        lines.append("")
        for param in skill.parameters:
            required_str = "" if param.required else " [可选]"
            lines.append(f"- `{param.name}`: ({param.type}) {param.description}{required_str}")
        lines.append("")

    if skill.prompt_template:
        lines.append("## 提示词模板")
        lines.append("")
        lines.append(skill.prompt_template)
        lines.append("")

    if skill.notes:
        lines.append("## 注意事项")
        lines.append("")
        for note in skill.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)
