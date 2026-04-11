"""Skill 注册表。"""

from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from backend.tools.skills.loader import SkillLoader, SkillLoaderError
from backend.tools.skills.models import SUPPORTED_METHOD_FAMILIES, Skill


class SkillRegistry:
    """管理 Skill 的发现、查询与启停。"""

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self._loader = SkillLoader(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._disabled_skills: set[str] = set()
        self._loaded = False

    def load_all(self, force_reload: bool = False) -> list[str]:
        """加载全部 Skill。"""

        if self._loaded and not force_reload:
            return list(self._skills.keys())

        self._skills.clear()
        loaded_names: list[str] = []
        for skill_name in self._loader.discover_skills():
            try:
                skill = self._loader.load_skill(skill_name, use_cache=not force_reload)
            except SkillLoaderError:
                loaded_names.append(skill_name)
                continue
            self._skills[skill.name] = skill
            loaded_names.append(skill.name)

        self._loaded = True
        return loaded_names

    def get(self, skill_name: str) -> Skill:
        """按名称获取 Skill。"""

        if not self._loaded:
            self.load_all()
        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")
        return self._skills[skill_name]

    def has(self, skill_name: str) -> bool:
        """Skill 是否存在。"""

        if not self._loaded:
            self.load_all()
        return skill_name in self._skills

    def list_skills(self) -> list[str]:
        """返回全部 Skill 名称。"""

        if not self._loaded:
            self.load_all()
        return sorted(self._skills.keys())

    def get_all_skills(self) -> list[Skill]:
        """返回全部 Skill。"""

        if not self._loaded:
            self.load_all()
        return list(self._skills.values())

    def get_by_category(self, category: str) -> list[Skill]:
        """按 category 获取 Skill。"""

        if not self._loaded:
            self.load_all()
        return [skill for skill in self._skills.values() if skill.metadata.category == category]

    def get_by_tag(self, tag: str) -> list[Skill]:
        """按标签获取 Skill。"""

        if not self._loaded:
            self.load_all()
        return [skill for skill in self._skills.values() if tag in skill.metadata.tags]

    def get_by_method_family(
        self,
        family: str,
        *,
        include_non_learned: bool = True,
        include_legacy: bool = True,
    ) -> list[Skill]:
        """按方法家族获取 Skill。"""

        if not self._loaded:
            self.load_all()

        results: list[Skill] = []
        normalized_family = family if family in SUPPORTED_METHOD_FAMILIES else "general"
        for skill in self._skills.values():
            if skill.metadata.normalized_method_family != normalized_family:
                continue
            if not include_non_learned and not skill.metadata.is_learned:
                continue
            if not include_legacy and skill.metadata.lifecycle_state == "legacy":
                continue
            results.append(skill)
        return results

    def search(self, query: str) -> list[Skill]:
        """文本搜索 Skill。"""

        if not self._loaded:
            self.load_all()

        query_lower = query.lower()
        results: list[Skill] = []
        for skill in self._skills.values():
            haystack = " ".join(
                [
                    skill.name,
                    skill.description,
                    skill.metadata.category,
                    skill.metadata.method_family,
                    skill.metadata.method_variant,
                    skill.capability.capability,
                    " ".join(skill.metadata.tags),
                ]
            ).lower()
            if query_lower in haystack:
                results.append(skill)
        return results

    def summarize_method_families(
        self,
        *,
        preferred_variants: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """按方法家族聚合摘要。"""

        if not self._loaded:
            self.load_all()

        preferred_variants = preferred_variants or {}
        grouped: dict[str, list[Skill]] = defaultdict(list)
        for skill in self._skills.values():
            family = skill.metadata.normalized_method_family
            grouped[family].append(skill)

        summaries: list[dict[str, Any]] = []
        for family in SUPPORTED_METHOD_FAMILIES:
            skills = grouped.get(family, [])
            enabled_skills = [skill for skill in skills if self.is_enabled(skill.name)]
            usage_count = sum(skill.metadata.usage_count for skill in skills)
            pass_rates = [skill.metadata.verifier_pass_rate for skill in skills if skill.metadata.verifier_pass_rate > 0]
            confidence_scores = [skill.metadata.confidence_score for skill in skills if skill.metadata.confidence_score > 0]
            descriptions = [skill.capability.capability or skill.description for skill in skills if skill.capability.capability or skill.description]
            summaries.append(
                {
                    "family": family,
                    "title": family,
                    "description": descriptions[0] if descriptions else self._family_description(family),
                    "variant_count": len(skills),
                    "active_count": len(
                        [skill for skill in skills if skill.metadata.lifecycle_state == "active"]
                    ),
                    "enabled_count": len(enabled_skills),
                    "recent_usage_count": usage_count,
                    "success_rate": round(sum(pass_rates) / len(pass_rates), 4) if pass_rates else 0.0,
                    "average_confidence": round(sum(confidence_scores) / len(confidence_scores), 4) if confidence_scores else 0.0,
                    "preferred_variant": preferred_variants.get(family, ""),
                }
            )
        return summaries

    def list_method_variants(
        self,
        family: str,
        *,
        preferred_variant: str = "",
        include_legacy: bool = True,
    ) -> list[dict[str, Any]]:
        """返回某个 family 下的变体详情。"""

        skills = self.get_by_method_family(family, include_non_learned=True, include_legacy=include_legacy)
        ranked = sorted(
            skills,
            key=lambda skill: self._variant_rank(skill, preferred_variant=preferred_variant),
        )
        return [self._skill_to_variant_payload(skill, preferred_variant=preferred_variant) for skill in ranked]

    def rank_families_for_query(self, query: str, top_n: int = 3) -> list[dict[str, Any]]:
        """根据查询文本对方法家族打分。"""

        summaries = self.summarize_method_families()
        query_lower = query.lower()
        scored: list[dict[str, Any]] = []
        for summary in summaries:
            family = str(summary["family"])
            score = 0.0
            if family.replace("_", " ") in query_lower:
                score += 2.0
            if family.split("_")[0] in query_lower:
                score += 1.0
            if family == "regression_analysis" and any(token in query_lower for token in ("回归", "regression", "logistic", "线性")):
                score += 2.0
            if family == "survival_analysis" and any(token in query_lower for token in ("生存", "kaplan", "cox", "log-rank")):
                score += 2.0
            if family == "descriptive_analysis" and any(token in query_lower for token in ("描述", "概览", "均值", "标准差")):
                score += 1.5
            if family == "statistical_test" and any(token in query_lower for token in ("检验", "t检验", "卡方", "anova")):
                score += 1.5
            score += float(summary.get("success_rate", 0.0)) * 0.5
            score += min(float(summary.get("recent_usage_count", 0)), 20.0) / 20.0
            summary["match_score"] = round(score, 4)
            scored.append(summary)

        scored.sort(key=lambda item: (-float(item["match_score"]), -float(item["success_rate"]), -int(item["variant_count"])))
        return scored[:top_n]

    def select_variants_for_query(
        self,
        *,
        family: str,
        query: str,
        top_k: int = 5,
        preferred_variant: str = "",
    ) -> list[Skill]:
        """在指定家族内为 query 选择候选变体。"""

        candidates = self.get_by_method_family(family, include_non_learned=True, include_legacy=False)
        ranked = sorted(
            candidates,
            key=lambda skill: self._variant_rank(
                skill,
                preferred_variant=preferred_variant,
                query=query,
            ),
        )
        return ranked[:top_k]

    def register_skill(self, skill: Skill) -> None:
        """注册 Skill。"""

        if skill.name in self._skills:
            raise ValueError(f"技能已存在: {skill.name}")
        self._skills[skill.name] = skill
        self._loaded = True

    def unregister_skill(self, skill_name: str) -> None:
        """注销 Skill。"""

        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")
        del self._skills[skill_name]
        self._disabled_skills.discard(skill_name)

    def get_openai_tools_definition(self) -> list[dict[str, Any]]:
        """导出 OpenAI 工具定义。"""

        if not self._loaded:
            self.load_all()
        return [skill.to_openai_tool_definition() for skill in self._skills.values()]

    def clear(self) -> None:
        """清空注册表。"""

        self._skills.clear()
        self._disabled_skills.clear()
        self._loaded = False
        self._loader.clear_cache()

    def is_enabled(self, skill_name: str) -> bool:
        """Skill 是否启用。"""

        if not self._loaded:
            self.load_all()
        return skill_name in self._skills and skill_name not in self._disabled_skills

    def enable(self, skill_name: str) -> None:
        """启用 Skill。"""

        if not self._loaded:
            self.load_all()
        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")
        self._disabled_skills.discard(skill_name)

    def disable(self, skill_name: str) -> None:
        """禁用 Skill。"""

        if not self._loaded:
            self.load_all()
        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")
        self._disabled_skills.add(skill_name)

    def _variant_rank(
        self,
        skill: Skill,
        *,
        preferred_variant: str = "",
        query: str = "",
    ) -> tuple[float, float, float, str]:
        preferred_bonus = 5.0 if preferred_variant and skill.metadata.method_variant == preferred_variant else 0.0
        lifecycle_penalty = {
            "active": 0.0,
            "candidate": -1.0,
            "legacy": -2.0,
            "deprecated": -4.0,
        }.get(skill.metadata.lifecycle_state, -1.0)
        query_score = 0.0
        if query:
            haystack = " ".join(
                [
                    skill.name,
                    skill.description,
                    skill.capability.capability,
                    skill.metadata.method_variant,
                    " ".join(skill.metadata.tags),
                ]
            ).lower()
            query_score = SequenceMatcher(None, query.lower(), haystack).ratio() * 2.0
        return (
            -(preferred_bonus + lifecycle_penalty + query_score + skill.metadata.verifier_pass_rate + skill.metadata.confidence_score),
            -float(skill.metadata.usage_count),
            -float(skill.metadata.verifier_pass_rate),
            skill.name,
        )

    def _skill_to_variant_payload(self, skill: Skill, *, preferred_variant: str = "") -> dict[str, Any]:
        return {
            "name": skill.name,
            "description": skill.description,
            "enabled": self.is_enabled(skill.name),
            "category": skill.metadata.category,
            "analysis_domain": skill.metadata.analysis_domain,
            "method_family": skill.metadata.normalized_method_family,
            "method_variant": skill.metadata.method_variant or skill.name,
            "process_signature": skill.metadata.process_signature,
            "input_schema_signature": skill.metadata.input_schema_signature,
            "verifier_family": skill.metadata.verifier_family,
            "provenance_trajectory_id": skill.metadata.provenance_trajectory_id,
            "confidence_score": skill.metadata.confidence_score,
            "lifecycle_state": skill.metadata.lifecycle_state,
            "last_used_at": skill.metadata.last_used_at,
            "usage_count": skill.metadata.usage_count,
            "verifier_pass_rate": skill.metadata.verifier_pass_rate,
            "capability": skill.capability.capability,
            "limitations": skill.capability.limitations,
            "applicable_scenarios": skill.capability.applicable_scenarios,
            "is_preferred": bool(preferred_variant and skill.metadata.method_variant == preferred_variant),
        }

    def _family_description(self, family: str) -> str:
        descriptions = {
            "descriptive_analysis": "描述统计、相关矩阵、数据概览与质量检查",
            "statistical_test": "假设检验、组间比较与显著性判断",
            "regression_analysis": "线性、Logistic 与广义回归建模",
            "survival_analysis": "Kaplan-Meier、Log-rank 与 Cox 生存分析",
            "epidemiology_analysis": "流行病学比率、队列与病例对照分析",
            "visualization": "统计图表与结果可视化",
            "general": "通用分析与兜底方法",
        }
        return descriptions.get(family, "通用分析方法")


_global_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """返回全局 Skill 注册表。"""

    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def reset_skill_registry() -> None:
    """重置全局 Skill 注册表。"""

    global _global_registry
    _global_registry = None
