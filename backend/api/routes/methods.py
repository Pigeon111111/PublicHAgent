"""方法家族与细分变体接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.learning.skill_learning import SkillLearningService
from backend.learning.trajectory import TrajectoryRecorder
from backend.storage.history_storage import get_history_storage
from backend.tools.skills.models import SUPPORTED_METHOD_FAMILIES
from backend.tools.skills.registry import get_skill_registry

router = APIRouter()


class MethodFamilySummary(BaseModel):
    """方法家族摘要。"""

    family: str
    title: str
    description: str
    variant_count: int
    active_count: int
    enabled_count: int
    recent_usage_count: int
    success_rate: float
    average_confidence: float
    preferred_variant: str = ""
    match_score: float = 0.0


class MethodVariant(BaseModel):
    """细分方法详情。"""

    name: str
    description: str
    enabled: bool
    category: str
    analysis_domain: str
    method_family: str
    method_variant: str
    process_signature: str
    input_schema_signature: str
    verifier_family: str
    provenance_trajectory_id: str
    confidence_score: float
    lifecycle_state: str
    last_used_at: str = ""
    usage_count: int = 0
    verifier_pass_rate: float = 0.0
    capability: str = ""
    limitations: list[str] = Field(default_factory=list)
    applicable_scenarios: list[str] = Field(default_factory=list)
    is_preferred: bool = False
    recent_evaluations: list[dict[str, Any]] = Field(default_factory=list)


class MethodFamilyListResponse(BaseModel):
    """方法家族列表响应。"""

    families: list[MethodFamilySummary]
    total: int


class MethodVariantListResponse(BaseModel):
    """方法变体列表响应。"""

    family: str
    preferred_variant: str = ""
    variants: list[MethodVariant]
    total: int


class PreferredVariantRequest(BaseModel):
    """偏好变体设置请求。"""

    preferred_variant: str = ""
    user_id: str = "default"


class PromoteVariantResponse(BaseModel):
    """晋升新变体响应。"""

    analysis_id: str
    skill_name: str
    family: str
    variant: str


@router.get("/method-families", response_model=MethodFamilyListResponse)
async def list_method_families(user_id: str = "default") -> MethodFamilyListResponse:
    storage = get_history_storage()
    registry = get_skill_registry()
    preferences = storage.list_preferred_variants(user_id=user_id)
    learning_service = SkillLearningService()
    learning_service.migrate_legacy_skills()
    families = [
        MethodFamilySummary(**payload)
        for payload in registry.summarize_method_families(preferred_variants=preferences)
    ]
    return MethodFamilyListResponse(families=families, total=len(families))


@router.get("/method-families/{family}/variants", response_model=MethodVariantListResponse)
async def list_method_variants(
    family: str,
    user_id: str = "default",
) -> MethodVariantListResponse:
    if family not in SUPPORTED_METHOD_FAMILIES:
        raise HTTPException(status_code=404, detail=f"方法家族不存在: {family}")

    storage = get_history_storage()
    registry = get_skill_registry()
    learning_service = SkillLearningService()
    learning_service.migrate_legacy_skills()

    preferred_variant = storage.get_preferred_variant(user_id=user_id, family=family)
    variants = registry.list_method_variants(family, preferred_variant=preferred_variant)
    hydrated_variants: list[MethodVariant] = []
    for variant in variants:
        recent_evaluations = storage.list_recent_evaluations_for_skill(str(variant["name"]), limit=5)
        variant["recent_evaluations"] = recent_evaluations
        hydrated_variants.append(MethodVariant(**variant))

    return MethodVariantListResponse(
        family=family,
        preferred_variant=preferred_variant,
        variants=hydrated_variants,
        total=len(hydrated_variants),
    )


@router.post("/method-families/{family}/preferred-variant")
async def set_preferred_variant(
    family: str,
    request: PreferredVariantRequest,
) -> dict[str, Any]:
    if family not in SUPPORTED_METHOD_FAMILIES:
        raise HTTPException(status_code=404, detail=f"方法家族不存在: {family}")

    storage = get_history_storage()
    result = storage.set_preferred_variant(
        user_id=request.user_id,
        family=family,
        preferred_variant=request.preferred_variant,
    )
    return {"success": True, "preference": result}


@router.post("/analysis/{analysis_id}/promote-variant", response_model=PromoteVariantResponse)
async def promote_analysis_variant(analysis_id: str) -> PromoteVariantResponse:
    storage = get_history_storage()
    record = storage.get_analysis_record(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"分析记录不存在: {analysis_id}")
    trajectory_id = str(record.get("trajectory_id") or "")
    if not trajectory_id:
        raise HTTPException(status_code=400, detail="该分析记录没有可学习的轨迹")

    recorder = TrajectoryRecorder()
    try:
        trajectory = recorder.load(trajectory_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"轨迹不存在: {trajectory_id}") from exc

    learning_service = SkillLearningService()
    skill_name = learning_service.promote_analysis_to_variant(trajectory)
    if not skill_name:
        raise HTTPException(status_code=400, detail="该分析未通过验证，无法晋升为新变体")

    evaluation = storage.get_evaluation_report(analysis_id)
    if evaluation is not None:
        report_json = dict(evaluation.get("report_json") or {})
        storage.upsert_evaluation_report(
            analysis_record_id=analysis_id,
            session_id=evaluation.get("session_id"),
            trajectory_id=evaluation.get("trajectory_id"),
            task_family=str(evaluation.get("task_family") or record.get("task_family") or ""),
            final_score=float(evaluation.get("final_score") or 0.0),
            passed=bool(evaluation.get("passed", False)),
            summary=str(evaluation.get("summary") or ""),
            report_json=report_json,
            associated_skill=skill_name,
        )

    registry = get_skill_registry()
    skill = registry.get(skill_name)
    return PromoteVariantResponse(
        analysis_id=analysis_id,
        skill_name=skill_name,
        family=skill.metadata.normalized_method_family,
        variant=skill.metadata.method_variant or skill.name,
    )
