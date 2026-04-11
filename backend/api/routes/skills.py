"""Skill 管理 API。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.tools.skills.loader import SkillLoader
from backend.tools.skills.models import (
    SUPPORTED_METHOD_FAMILIES,
    Skill,
    SkillCapability,
    SkillLifecycleState,
    SkillMetadata,
    SkillParameter,
)
from backend.tools.skills.registry import get_skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillMetadataPayload(BaseModel):
    """Skill 元数据载荷。"""

    name: str
    version: str
    description: str
    author: str
    tags: list[str] = Field(default_factory=list)
    category: str
    min_python_version: str
    dependencies: list[str] = Field(default_factory=list)
    analysis_domain: str = "general"
    method_family: str = "general"
    method_variant: str = ""
    process_signature: str = ""
    input_schema_signature: str = ""
    verifier_family: str = ""
    provenance_trajectory_id: str = ""
    confidence_score: float = 0.0
    lifecycle_state: str = "active"
    last_used_at: str = ""
    usage_count: int = 0
    verifier_pass_rate: float = 0.0


class CreateSkillRequest(BaseModel):
    """创建 Skill 请求。"""

    name: str
    description: str
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    capability: str
    limitations: list[str] = Field(default_factory=list)
    applicable_scenarios: list[str] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    prompt_template: str = ""
    notes: list[str] = Field(default_factory=list)
    author: str = ""
    dependencies: list[str] = Field(default_factory=list)
    analysis_domain: str = "general"
    method_family: str = "general"
    method_variant: str = ""
    process_signature: str = ""
    input_schema_signature: str = ""
    verifier_family: str = ""
    provenance_trajectory_id: str = ""
    confidence_score: float = 0.0
    lifecycle_state: str = "active"
    last_used_at: str = ""
    usage_count: int = 0
    verifier_pass_rate: float = 0.0


class UpdateSkillRequest(BaseModel):
    """更新 Skill 请求。"""

    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    capability: str | None = None
    limitations: list[str] | None = None
    applicable_scenarios: list[str] | None = None
    parameters: list[dict[str, Any]] | None = None
    prompt_template: str | None = None
    notes: list[str] | None = None
    author: str | None = None
    dependencies: list[str] | None = None
    analysis_domain: str | None = None
    method_family: str | None = None
    method_variant: str | None = None
    process_signature: str | None = None
    input_schema_signature: str | None = None
    verifier_family: str | None = None
    provenance_trajectory_id: str | None = None
    confidence_score: float | None = None
    lifecycle_state: str | None = None
    last_used_at: str | None = None
    usage_count: int | None = None
    verifier_pass_rate: float | None = None


def _normalize_method_family(family: str | None) -> str:
    value = (family or "").strip() or "general"
    if value not in SUPPORTED_METHOD_FAMILIES:
        return "general"
    return value


def _normalize_lifecycle_state(value: str | None) -> SkillLifecycleState:
    lifecycle = (value or "active").strip()
    if lifecycle == "candidate":
        return "candidate"
    if lifecycle == "deprecated":
        return "deprecated"
    if lifecycle == "legacy":
        return "legacy"
    return "active"


def _serialize_skill(skill: Skill, *, enabled: bool) -> dict[str, Any]:
    metadata = skill.metadata
    return {
        "name": skill.name,
        "description": skill.description,
        "enabled": enabled,
        "metadata": SkillMetadataPayload(
            name=metadata.name,
            version=metadata.version,
            description=metadata.description,
            author=metadata.author,
            tags=metadata.tags,
            category=metadata.category,
            min_python_version=metadata.min_python_version,
            dependencies=metadata.dependencies,
            analysis_domain=metadata.analysis_domain,
            method_family=metadata.normalized_method_family,
            method_variant=metadata.method_variant,
            process_signature=metadata.process_signature,
            input_schema_signature=metadata.input_schema_signature,
            verifier_family=metadata.verifier_family,
            provenance_trajectory_id=metadata.provenance_trajectory_id,
            confidence_score=metadata.confidence_score,
            lifecycle_state=metadata.lifecycle_state,
            last_used_at=metadata.last_used_at,
            usage_count=metadata.usage_count,
            verifier_pass_rate=metadata.verifier_pass_rate,
        ).model_dump(),
        "capability": {
            "capability": skill.capability.capability,
            "limitations": skill.capability.limitations,
            "applicable_scenarios": skill.capability.applicable_scenarios,
        },
        "parameters": [
            {
                "name": parameter.name,
                "type": parameter.type,
                "description": parameter.description,
                "required": parameter.required,
                "default": parameter.default,
                "enum": parameter.enum,
            }
            for parameter in skill.parameters
        ],
        "notes": skill.notes,
    }


def _build_parameters(parameters: list[dict[str, Any]]) -> list[SkillParameter]:
    return [
        SkillParameter(
            name=str(item.get("name", "")),
            type=str(item.get("type", "string")),
            description=str(item.get("description", "")),
            required=bool(item.get("required", True)),
            default=item.get("default"),
            enum=item.get("enum"),
        )
        for item in parameters
    ]


@router.get("")
async def list_skills() -> dict[str, Any]:
    """列出所有 Skill。"""
    try:
        registry = get_skill_registry()
        payload = [
            _serialize_skill(registry.get(name), enabled=registry.is_enabled(name))
            for name in registry.list_skills()
        ]
        return {"success": True, "skills": payload, "total": len(payload)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取 Skill 列表失败: {exc}") from exc


@router.get("/{skill_name}")
async def get_skill(skill_name: str) -> dict[str, Any]:
    """获取单个 Skill 详情。"""
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")
        skill = registry.get(skill_name)
        return {
            "success": True,
            "skill": _serialize_skill(skill, enabled=registry.is_enabled(skill_name)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取 Skill 详情失败: {exc}") from exc


@router.post("")
async def create_skill(request: CreateSkillRequest) -> dict[str, Any]:
    """创建 Skill。"""
    try:
        registry = get_skill_registry()
        if registry.has(request.name):
            raise HTTPException(status_code=400, detail=f"Skill 已存在: {request.name}")

        skill = Skill(
            metadata=SkillMetadata(
                name=request.name,
                description=request.description,
                category=request.category,
                tags=request.tags,
                author=request.author,
                dependencies=request.dependencies,
                analysis_domain=request.analysis_domain,
                method_family=_normalize_method_family(request.method_family),
                method_variant=request.method_variant,
                process_signature=request.process_signature,
                input_schema_signature=request.input_schema_signature,
                verifier_family=request.verifier_family,
                provenance_trajectory_id=request.provenance_trajectory_id,
                confidence_score=request.confidence_score,
                lifecycle_state=_normalize_lifecycle_state(request.lifecycle_state),
                last_used_at=request.last_used_at,
                usage_count=request.usage_count,
                verifier_pass_rate=request.verifier_pass_rate,
            ),
            capability=SkillCapability(
                capability=request.capability,
                limitations=request.limitations,
                applicable_scenarios=request.applicable_scenarios,
            ),
            parameters=_build_parameters(request.parameters),
            prompt_template=request.prompt_template,
            notes=request.notes,
        )

        skill_dir = Path(__file__).parent.parent.parent / "tools" / "skills" / request.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(_generate_skill_markdown(skill), encoding="utf-8")

        loader = SkillLoader()
        loaded_skill = loader.load_skill(request.name, use_cache=False)
        if registry.has(loaded_skill.name):
            registry.unregister_skill(loaded_skill.name)
        registry.register_skill(loaded_skill)
        return {
            "success": True,
            "message": f"Skill 创建成功: {request.name}",
            "skill": _serialize_skill(loaded_skill, enabled=registry.is_enabled(loaded_skill.name)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建 Skill 失败: {exc}") from exc


@router.put("/{skill_name}")
async def update_skill(skill_name: str, request: UpdateSkillRequest) -> dict[str, Any]:
    """更新 Skill。"""
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")

        loader = SkillLoader()
        skill = loader.load_skill(skill_name, use_cache=False)
        metadata = skill.metadata

        if request.description is not None:
            metadata.description = request.description
        if request.category is not None:
            metadata.category = request.category
        if request.tags is not None:
            metadata.tags = request.tags
        if request.author is not None:
            metadata.author = request.author
        if request.dependencies is not None:
            metadata.dependencies = request.dependencies
        if request.analysis_domain is not None:
            metadata.analysis_domain = request.analysis_domain
        if request.method_family is not None:
            metadata.method_family = _normalize_method_family(request.method_family)
        if request.method_variant is not None:
            metadata.method_variant = request.method_variant
        if request.process_signature is not None:
            metadata.process_signature = request.process_signature
        if request.input_schema_signature is not None:
            metadata.input_schema_signature = request.input_schema_signature
        if request.verifier_family is not None:
            metadata.verifier_family = request.verifier_family
        if request.provenance_trajectory_id is not None:
            metadata.provenance_trajectory_id = request.provenance_trajectory_id
        if request.confidence_score is not None:
            metadata.confidence_score = request.confidence_score
        if request.lifecycle_state is not None:
            metadata.lifecycle_state = _normalize_lifecycle_state(request.lifecycle_state)
        if request.last_used_at is not None:
            metadata.last_used_at = request.last_used_at
        if request.usage_count is not None:
            metadata.usage_count = request.usage_count
        if request.verifier_pass_rate is not None:
            metadata.verifier_pass_rate = request.verifier_pass_rate

        if request.capability is not None:
            skill.capability.capability = request.capability
        if request.limitations is not None:
            skill.capability.limitations = request.limitations
        if request.applicable_scenarios is not None:
            skill.capability.applicable_scenarios = request.applicable_scenarios
        if request.parameters is not None:
            skill.parameters = _build_parameters(request.parameters)
        if request.prompt_template is not None:
            skill.prompt_template = request.prompt_template
        if request.notes is not None:
            skill.notes = request.notes

        skill_dir = Path(__file__).parent.parent.parent / "tools" / "skills" / skill_name
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(_generate_skill_markdown(skill), encoding="utf-8")

        loaded_skill = loader.reload_skill(skill_name)
        if registry.has(skill_name):
            registry.unregister_skill(skill_name)
        registry.register_skill(loaded_skill)
        return {"success": True, "message": f"Skill 更新成功: {skill_name}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新 Skill 失败: {exc}") from exc


@router.delete("/{skill_name}")
async def delete_skill(skill_name: str) -> dict[str, Any]:
    """删除 Skill。"""
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
        return {"success": True, "message": f"Skill 删除成功: {skill_name}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除 Skill 失败: {exc}") from exc


@router.post("/{skill_name}/enable")
async def enable_skill(skill_name: str) -> dict[str, Any]:
    """启用 Skill。"""
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")
        registry.enable(skill_name)
        return {"success": True, "message": f"Skill 已启用: {skill_name}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启用 Skill 失败: {exc}") from exc


@router.post("/{skill_name}/disable")
async def disable_skill(skill_name: str) -> dict[str, Any]:
    """禁用 Skill。"""
    try:
        registry = get_skill_registry()
        if not registry.has(skill_name):
            raise HTTPException(status_code=404, detail=f"Skill 不存在: {skill_name}")
        registry.disable(skill_name)
        return {"success": True, "message": f"Skill 已禁用: {skill_name}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"禁用 Skill 失败: {exc}") from exc


@router.get("/capabilities/all")
async def get_all_capabilities() -> dict[str, Any]:
    """获取全部 Skill 能力描述。"""
    try:
        registry = get_skill_registry()
        payload = {
            name: _serialize_skill(registry.get(name), enabled=registry.is_enabled(name))
            for name in registry.list_skills()
        }
        return {"success": True, "capabilities": payload}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取能力描述失败: {exc}") from exc


def _generate_skill_markdown(skill: Skill) -> str:
    """生成 Skill Markdown 文件。"""
    metadata = skill.metadata
    lines = [
        "---",
        f"name: {metadata.name}",
        f"version: {metadata.version}",
        f"description: {metadata.description}",
        f"author: {metadata.author}",
        "tags:",
    ]
    for tag in metadata.tags:
        lines.append(f"  - {tag}")
    lines.extend(
        [
            f"category: {metadata.category}",
            f'min_python_version: "{metadata.min_python_version}"',
            "dependencies:",
        ]
    )
    for dependency in metadata.dependencies:
        lines.append(f"  - {dependency}")
    lines.extend(
        [
            f"analysis_domain: {metadata.analysis_domain}",
            f"method_family: {metadata.normalized_method_family}",
            f"method_variant: {metadata.method_variant}",
            f"process_signature: {metadata.process_signature}",
            f"input_schema_signature: {metadata.input_schema_signature}",
            f"verifier_family: {metadata.verifier_family}",
            f"provenance_trajectory_id: {metadata.provenance_trajectory_id}",
            f"confidence_score: {metadata.confidence_score}",
            f"lifecycle_state: {metadata.lifecycle_state}",
            f'last_used_at: "{metadata.last_used_at}"',
            f"usage_count: {metadata.usage_count}",
            f"verifier_pass_rate: {metadata.verifier_pass_rate}",
            "---",
            "",
            f"# {metadata.name}",
            "",
            "## 能力描述",
            "",
            f"**能力范围**：{skill.capability.capability}",
            "",
            f"**方法家族**：{metadata.normalized_method_family}",
            f"**细分方法**：{metadata.method_variant or metadata.name}",
            f"**生命周期**：{metadata.lifecycle_state}",
            "",
        ]
    )
    if skill.capability.limitations:
        lines.append("**限制条件**：")
        for item in skill.capability.limitations:
            lines.append(f"- {item}")
        lines.append("")
    if skill.capability.applicable_scenarios:
        lines.append("**适用场景**：")
        for item in skill.capability.applicable_scenarios:
            lines.append(f"- {item}")
        lines.append("")
    if skill.parameters:
        lines.extend(["## 参数", ""])
        for parameter in skill.parameters:
            required_text = "必填" if parameter.required else "可选"
            lines.append(f"- `{parameter.name}` ({parameter.type}, {required_text})：{parameter.description}")
        lines.append("")
    if skill.prompt_template:
        lines.extend(["## 提示词模板", "", skill.prompt_template, ""])
    if skill.notes:
        lines.extend(["## 注意事项", ""])
        for note in skill.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)
