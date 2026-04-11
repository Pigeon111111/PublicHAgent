"""从成功分析轨迹中学习可复用的分层 Skill。"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import suppress
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from backend.learning.trajectory import AnalysisTrajectory
from backend.tools.skills.loader import SkillLoader
from backend.tools.skills.models import SUPPORTED_METHOD_FAMILIES, Skill
from backend.tools.skills.registry import get_skill_registry

AUTO_ACTIVE_FAMILIES = {
    "descriptive_analysis",
    "regression_analysis",
    "survival_analysis",
}


class SkillLearningService:
    """Skill 学习与分层检索服务。"""

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else Path("backend/tools/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._loader = SkillLoader(self.skills_dir)
        self._registry = get_skill_registry()

    def migrate_legacy_skills(self) -> int:
        """把旧 learned_* Skill 迁移到新元数据体系。"""

        migrated = 0
        for skill_name in self._loader.discover_skills():
            skill = self._loader.load_skill(skill_name, use_cache=False)
            metadata = skill.metadata
            if not metadata.is_learned:
                continue
            if metadata.method_family and metadata.lifecycle_state:
                continue

            metadata.category = "learned-analysis"
            metadata.method_family = self._guess_method_family_from_text(
                " ".join([skill.name, skill.description, skill.capability.capability, " ".join(metadata.tags)])
            )
            metadata.method_variant = metadata.method_variant or self._guess_method_variant(
                metadata.method_family,
                " ".join([skill.name, skill.description, skill.capability.capability]),
                {},
            )
            metadata.verifier_family = metadata.verifier_family or metadata.method_family
            metadata.lifecycle_state = "legacy"
            metadata.analysis_domain = metadata.analysis_domain or "public_health"
            self._write_skill(skill)
            migrated += 1

        if migrated:
            self._registry.clear()
            self._registry.load_all(force_reload=True)
        return migrated

    def learn_from_trajectory(
        self,
        trajectory: AnalysisTrajectory,
        *,
        force_new_variant: bool = False,
    ) -> str | None:
        """从成功轨迹生成或更新 Skill。"""

        if not trajectory.success:
            return None

        evaluation = trajectory.evaluation_report or {}
        if not bool(evaluation.get("passed", trajectory.validation.passed)):
            return None

        family = self._resolve_method_family(trajectory)
        variant = self._guess_method_variant(
            family,
            trajectory.user_query,
            evaluation,
            trajectory=trajectory,
        )
        process_signature = self._build_process_signature(trajectory, family=family, variant=variant)
        input_schema_signature = self._build_input_schema_signature(trajectory, evaluation)
        lifecycle_state = self._determine_lifecycle_state(family=family, evaluation=evaluation)
        confidence = self._estimate_confidence(trajectory)
        existing_skill = None if force_new_variant else self._find_matching_skill(
            family=family,
            variant=variant,
            process_signature=process_signature,
        )

        if existing_skill is not None:
            skill_name = existing_skill.name
            skill_dir = self.skills_dir / skill_name
        else:
            skill_name = self._choose_skill_name(family=family, variant=variant, process_signature=process_signature)
            skill_dir = self.skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

        content = self._build_skill_markdown(
            skill_name=skill_name,
            trajectory=trajectory,
            family=family,
            variant=variant,
            process_signature=process_signature,
            input_schema_signature=input_schema_signature,
            lifecycle_state=lifecycle_state,
            confidence_score=confidence,
            existing_skill=existing_skill,
        )
        self._security_check(content)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

        loaded_skill = self._loader.load_skill(skill_name, use_cache=False)
        if self._registry.has(loaded_skill.name):
            self._registry.unregister_skill(loaded_skill.name)
        self._registry.register_skill(loaded_skill)
        if lifecycle_state == "active":
            self._registry.enable(loaded_skill.name)
        else:
            self._registry.disable(loaded_skill.name)

        return loaded_skill.name

    def promote_analysis_to_variant(self, trajectory: AnalysisTrajectory) -> str | None:
        """把一次成功分析强制分裂为新 variant。"""

        return self.learn_from_trajectory(trajectory, force_new_variant=True)

    def demote_skill(self, skill_name: str) -> None:
        """把 Skill 降级为 candidate。"""

        skill = self._loader.load_skill(skill_name, use_cache=False)
        skill.metadata.lifecycle_state = "candidate"
        self._write_skill(skill)
        if self._registry.has(skill_name):
            with suppress(KeyError):
                self._registry.disable(skill_name)
            self._registry.unregister_skill(skill_name)
        updated = self._loader.load_skill(skill_name, use_cache=False)
        self._registry.register_skill(updated)
        self._registry.disable(updated.name)

    def find_reusable_skill(
        self,
        query: str,
        *,
        family: str | None = None,
        preferred_variant: str = "",
    ) -> str | None:
        """分层检索可复用 Skill，最后退回扁平召回。"""

        self.migrate_legacy_skills()
        registry = get_skill_registry()
        normalized_family = family or self._guess_method_family_from_text(query)
        if normalized_family in SUPPORTED_METHOD_FAMILIES:
            candidates = registry.select_variants_for_query(
                family=normalized_family,
                query=query,
                preferred_variant=preferred_variant,
            )
            for skill in candidates:
                if skill.metadata.lifecycle_state == "deprecated":
                    continue
                if not registry.is_enabled(skill.name) and skill.metadata.lifecycle_state != "active":
                    continue
                return skill.name

        query_terms = set(self._tokenize(query))
        if not query_terms:
            return None

        for skill in registry.get_all_skills():
            if not skill.metadata.is_learned:
                continue
            haystack = " ".join(
                [
                    skill.name,
                    skill.description,
                    skill.capability.capability,
                    skill.metadata.method_family,
                    skill.metadata.method_variant,
                    " ".join(skill.metadata.tags),
                ]
            )
            if query_terms & set(self._tokenize(haystack)):
                return skill.name
        return None

    def build_family_context(
        self,
        query: str,
        *,
        preferred_variants: dict[str, str] | None = None,
        top_n: int = 3,
        top_k_variants: int = 5,
    ) -> dict[str, Any]:
        """构建 Planner 渐进披露上下文。"""

        self.migrate_legacy_skills()
        registry = get_skill_registry()
        preferred_variants = preferred_variants or {}
        family_summaries = registry.rank_families_for_query(query, top_n=top_n)
        expanded_family = family_summaries[0]["family"] if family_summaries else "general"
        variants = [
            registry._skill_to_variant_payload(skill, preferred_variant=preferred_variants.get(expanded_family, ""))  # noqa: SLF001
            for skill in registry.select_variants_for_query(
                family=str(expanded_family),
                query=query,
                top_k=top_k_variants,
                preferred_variant=preferred_variants.get(str(expanded_family), ""),
            )
        ]
        return {
            "families": family_summaries,
            "expanded_family": expanded_family,
            "variants": variants,
            "needs_new_variant": len(variants) == 0,
        }

    def _resolve_method_family(self, trajectory: AnalysisTrajectory) -> str:
        family = (trajectory.task_family or trajectory.intent or "").strip()
        if family in SUPPORTED_METHOD_FAMILIES:
            return family
        return self._guess_method_family_from_text(trajectory.user_query)

    def _guess_method_family_from_text(self, text: str) -> str:
        normalized = (text or "").lower()
        if any(token in normalized for token in ("survival", "kaplan", "cox", "log-rank", "生存", "随访")):
            return "survival_analysis"
        if any(token in normalized for token in ("regression", "logistic", "linear", "回归", "glm")):
            return "regression_analysis"
        if any(token in normalized for token in ("anova", "卡方", "t检验", "假设检验", "检验")):
            return "statistical_test"
        if any(token in normalized for token in ("plot", "chart", "图", "可视化", "柱状图", "折线图")):
            return "visualization"
        if any(token in normalized for token in ("cohort", "case-control", "epidemiology", "队列", "病例对照", "流行病学")):
            return "epidemiology_analysis"
        if any(token in normalized for token in ("mean", "median", "std", "描述", "均值", "标准差", "概览")):
            return "descriptive_analysis"
        return "general"

    def _guess_method_variant(
        self,
        family: str,
        query: str,
        evaluation: dict[str, Any],
        *,
        trajectory: AnalysisTrajectory | None = None,
    ) -> str:
        normalized = " ".join(
            [
                query or "",
                json.dumps(evaluation, ensure_ascii=False),
                trajectory.plan_summary if trajectory is not None else "",
            ]
        ).lower()

        if family == "regression_analysis":
            if any(token in normalized for token in ("logistic", "二分类", "odds", "or ")):
                return "logistic_regression"
            if "poisson" in normalized:
                return "poisson_regression"
            return "linear_regression"
        if family == "survival_analysis":
            if "cox" in normalized or "hr" in normalized or "hazard ratio" in normalized:
                return "cox_ph"
            if "kaplan" in normalized or "log-rank" in normalized or "km" in normalized or "生存曲线" in normalized:
                return "km_logrank"
            return "survival_overview"
        if family == "descriptive_analysis":
            if "correlation" in normalized or "相关" in normalized:
                return "descriptive_with_correlation"
            return "descriptive_overview"
        if family == "statistical_test":
            if "anova" in normalized:
                return "anova"
            if "chi" in normalized or "卡方" in normalized:
                return "chi_square_test"
            if "paired" in normalized:
                return "paired_t_test"
            return "t_test"
        if family == "visualization":
            if "heatmap" in normalized or "热图" in normalized:
                return "heatmap_visualization"
            if "scatter" in normalized or "散点" in normalized:
                return "scatter_visualization"
            return "chart_visualization"
        if family == "epidemiology_analysis":
            if "propensity" in normalized or "倾向评分" in normalized:
                return "propensity_score_analysis"
            return "epidemiology_overview"
        return "general_analysis"

    def _build_process_signature(
        self,
        trajectory: AnalysisTrajectory,
        *,
        family: str,
        variant: str,
    ) -> str:
        step_tokens = [attempt.description.strip().lower() for attempt in trajectory.attempts if attempt.description.strip()]
        import_tokens = []
        metric_tokens = []
        for attempt in trajectory.attempts:
            code = attempt.code.lower()
            import_tokens.extend(sorted(set(re.findall(r"import\s+([a-zA-Z0-9_\.]+)", code))))
            metric_tokens.extend(sorted(set(re.findall(r"(r_squared|auc|hazard ratio|median_survival|p_value|log_rank)", code))))

        payload = "|".join(
            [
                family,
                variant,
                ">".join(step_tokens[:8]),
                ",".join(import_tokens[:8]),
                ",".join(metric_tokens[:8]),
            ]
        )
        digest = hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"{variant}:{digest}"

    def _build_input_schema_signature(
        self,
        trajectory: AnalysisTrajectory,
        evaluation: dict[str, Any],
    ) -> str:
        columns: list[str] = []
        for assertion in evaluation.get("metric_assertions", []):
            metric = str(assertion.get("metric", ""))
            if metric.startswith("schema.columns."):
                columns.append(metric.split(".", 2)[-1])
        if not columns:
            for data_file in trajectory.data_files[:1]:
                path = Path(data_file)
                if path.exists() and path.suffix.lower() == ".csv":
                    try:
                        header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
                        columns = [item.strip() for item in header.split(",") if item.strip()]
                    except Exception:  # noqa: BLE001
                        columns = []
        payload = "|".join(sorted(columns)[:20]) or trajectory.user_query[:120]
        digest = hashlib.sha1(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"schema:{digest}"

    def _estimate_confidence(self, trajectory: AnalysisTrajectory) -> float:
        evaluation = trajectory.evaluation_report or {}
        base = float(evaluation.get("final_score", 0.0) or 0.0)
        attempts_penalty = max(len(trajectory.attempts) - 1, 0) * 0.05
        return round(max(0.1, min(1.0, base - attempts_penalty)), 4)

    def _determine_lifecycle_state(self, *, family: str, evaluation: dict[str, Any]) -> str:
        if family in AUTO_ACTIVE_FAMILIES and bool(evaluation.get("passed")):
            return "active"
        return "candidate"

    def _find_matching_skill(
        self,
        *,
        family: str,
        variant: str,
        process_signature: str,
    ) -> Skill | None:
        best_skill: Skill | None = None
        best_score = 0.0
        for skill in self._registry.get_by_method_family(family, include_non_learned=False, include_legacy=False):
            if skill.metadata.method_variant != variant:
                continue
            similarity = SequenceMatcher(None, skill.metadata.process_signature, process_signature).ratio()
            if similarity > best_score:
                best_score = similarity
                best_skill = skill
        if best_score >= 0.9:
            return best_skill
        return None

    def _choose_skill_name(self, *, family: str, variant: str, process_signature: str) -> str:
        digest = hashlib.sha1(process_signature.encode("utf-8", errors="ignore")).hexdigest()[:8]
        family_slug = self._slugify(family)
        variant_slug = self._slugify(variant)
        return f"learned_{family_slug}_{variant_slug}_{digest}"

    def _build_skill_markdown(
        self,
        *,
        skill_name: str,
        trajectory: AnalysisTrajectory,
        family: str,
        variant: str,
        process_signature: str,
        input_schema_signature: str,
        lifecycle_state: str,
        confidence_score: float,
        existing_skill: Skill | None,
    ) -> str:
        method = trajectory.user_query.strip().replace("\n", " ")
        data_files = "\n".join(f"- `{Path(path).name}`" for path in trajectory.data_files) or "- 无"
        successful_attempts = [attempt for attempt in trajectory.attempts if attempt.success]
        last_attempt = successful_attempts[-1] if successful_attempts else trajectory.attempts[-1]
        output_files = last_attempt.artifacts.get("output_files", [])
        output_lines = "\n".join(f"- `{Path(str(path)).name}`" for path in output_files) or "- `analysis_report.md`\n- `analysis_result.json`"
        code_template = last_attempt.code.strip()
        if len(code_template) > 8000:
            code_template = code_template[:8000] + "\n# 代码过长，已截断，请查看原始轨迹。"

        usage_count = (existing_skill.metadata.usage_count if existing_skill else 0) + 1
        pass_rate = float((trajectory.evaluation_report or {}).get("final_score", 0.0) or 0.0)
        metadata_lines = [
            "---",
            f"name: {skill_name}",
            "version: 1.0.0",
            f"description: 从成功分析轨迹学习得到的 {family}/{variant} 方法",
            "author: PubHAgent",
            "tags:",
            "  - learned",
            "  - data-analysis",
            f"  - {family}",
            f"  - {variant}",
            "category: learned-analysis",
            'min_python_version: "3.10"',
            "dependencies:",
            "  - pandas",
            "  - numpy",
            "  - scipy",
            "analysis_domain: public_health",
            f"method_family: {family}",
            f"method_variant: {variant}",
            f"process_signature: {process_signature}",
            f"input_schema_signature: {input_schema_signature}",
            f"verifier_family: {family}",
            f"provenance_trajectory_id: {trajectory.trajectory_id}",
            f"confidence_score: {confidence_score}",
            f"lifecycle_state: {lifecycle_state}",
            f"last_used_at: {datetime.now().isoformat()}",
            f"usage_count: {usage_count}",
            f"verifier_pass_rate: {round(pass_rate, 4)}",
            "---",
            "",
            f"# {skill_name}",
            "",
            "## 能力描述",
            "",
            f"**能力范围**：复用以下成功分析方法：{method}",
            "",
            "**限制条件**：",
            "- 仅适用于结构化表格数据。",
            "- 默认读取会话输入目录中的 CSV、Excel、JSON、Parquet 或 Feather 文件。",
            "- 统计结论需要结合领域背景复核。",
            "",
            "**适用场景**：",
            f"- 用户需求与 `{family}` 家族相关。",
            f"- 细分方法优先选择 `{variant}`。",
            "- 需要复用已有成功路径并保留家族专用评估器约束。",
            "",
            "## 参数",
            "",
            "- `input_files`: (array) 会话输入文件列表",
            "- `output_dir`: (string) 输出目录",
            "- `analysis_goal`: (string) 分析目标",
            "",
            "## 提示词模板",
            "",
            "你正在复用 PubHAgent 已学习的分层 Skill。",
            f"方法家族：{family}",
            f"细分方法：{variant}",
            f"流程签名：{process_signature}",
            "",
            "输入数据示例：",
            data_files,
            "",
            "执行要求：",
            "1. 优先复用该 Skill 的代码模板和输出契约。",
            "2. 输出 analysis_report.md 和 analysis_result.json。",
            "3. 若输入字段与历史结构不完全一致，应先解释差异，再选择降级方案或学习新变体。",
            "",
            "## 代码模板",
            "",
            "```python",
            code_template,
            "```",
            "",
            "## 输出产物",
            "",
            output_lines,
            "",
            "## 注意事项",
            "",
            f"- 该 Skill 来源于轨迹 `{trajectory.trajectory_id}`。",
            f"- 该 Skill 的生命周期状态为 `{lifecycle_state}`。",
        ]
        return "\n".join(metadata_lines)

    def _write_skill(self, skill: Skill) -> None:
        skill_dir = self.skills_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = self._serialize_skill(skill)
        self._security_check(content)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def _serialize_skill(self, skill: Skill) -> str:
        lines = [
            "---",
            f"name: {skill.metadata.name}",
            f"version: {skill.metadata.version}",
            f"description: {skill.metadata.description}",
            f"author: {skill.metadata.author}",
            "tags:",
        ]
        for tag in skill.metadata.tags:
            lines.append(f"  - {tag}")
        lines.extend(
            [
                f"category: {skill.metadata.category}",
                f'min_python_version: "{skill.metadata.min_python_version}"',
                "dependencies:",
            ]
        )
        for dependency in skill.metadata.dependencies:
            lines.append(f"  - {dependency}")
        lines.extend(
            [
                f"analysis_domain: {skill.metadata.analysis_domain}",
                f"method_family: {skill.metadata.normalized_method_family}",
                f"method_variant: {skill.metadata.method_variant}",
                f"process_signature: {skill.metadata.process_signature}",
                f"input_schema_signature: {skill.metadata.input_schema_signature}",
                f"verifier_family: {skill.metadata.verifier_family}",
                f"provenance_trajectory_id: {skill.metadata.provenance_trajectory_id}",
                f"confidence_score: {skill.metadata.confidence_score}",
                f"lifecycle_state: {skill.metadata.lifecycle_state}",
                f"last_used_at: {skill.metadata.last_used_at}",
                f"usage_count: {skill.metadata.usage_count}",
                f"verifier_pass_rate: {skill.metadata.verifier_pass_rate}",
                "---",
                "",
                f"# {skill.name}",
                "",
                "## 能力描述",
                "",
                f"**能力范围**：{skill.capability.capability}",
                "",
            ]
        )
        if skill.capability.limitations:
            lines.append("**限制条件**：")
            lines.extend(f"- {item}" for item in skill.capability.limitations)
            lines.append("")
        if skill.capability.applicable_scenarios:
            lines.append("**适用场景**：")
            lines.extend(f"- {item}" for item in skill.capability.applicable_scenarios)
            lines.append("")
        if skill.parameters:
            lines.append("## 参数")
            lines.append("")
            for parameter in skill.parameters:
                required_marker = "" if parameter.required else " [可选]"
                lines.append(f"- `{parameter.name}`: ({parameter.type}) {parameter.description}{required_marker}")
            lines.append("")
        if skill.prompt_template:
            lines.extend(["## 提示词模板", "", skill.prompt_template, ""])
        if skill.notes:
            lines.append("## 注意事项")
            lines.append("")
            lines.extend(f"- {note}" for note in skill.notes)
            lines.append("")
        return "\n".join(lines)

    def _security_check(self, content: str) -> None:
        blocked_patterns = [
            r"api[_-]?key\s*=",
            r"password\s*=",
            r"token\s*=",
            r"subprocess\.",
            r"import\s+os\b",
            r"shutil\.rmtree",
        ]
        for pattern in blocked_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise ValueError(f"自动生成 Skill 未通过安全检查: {pattern}")

    def _slugify(self, text: str) -> str:
        words = self._tokenize(text)
        if not words:
            return "method"
        return "_".join(words[:6])

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.lower()
        ascii_words = re.findall(r"[a-z0-9]+", normalized)
        chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
        stop_words = {"the", "and", "for", "with", "data", "analysis", "分析", "数据", "方法"}
        tokens = ascii_words + chinese_chunks
        return [token for token in tokens if token not in stop_words]

    def build_variant_display_name(self, skill: Skill) -> str:
        """返回前端友好的变体名。"""

        variant = skill.metadata.method_variant or skill.name
        return variant.replace("_", " ")
