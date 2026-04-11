"""产物完整性检查。"""

from __future__ import annotations

from pathlib import Path

from backend.evaluation.checks.schema_checks import run_schema_checks
from backend.evaluation.schemas import ArtifactBundle, CheckResult, EvaluationFinding, TaskSpec


def run_artifact_checks(bundle: ArtifactBundle, spec: TaskSpec) -> CheckResult:
    """验证核心产物是否完整。"""
    findings: list[EvaluationFinding] = []
    hard_failures: list[str] = []
    score = 1.0

    if bundle.report_path is None:
        hard_failures.append("缺少 analysis_report.md")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="artifact",
                code="missing_report",
                message="未生成 analysis_report.md",
            )
        )
        score -= 0.35
    elif not Path(bundle.report_path).exists() or Path(bundle.report_path).stat().st_size == 0:
        hard_failures.append("analysis_report.md 不存在或为空")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="artifact",
                code="empty_report",
                message="analysis_report.md 不存在或为空",
            )
        )
        score -= 0.35

    if bundle.result_json_path is None:
        hard_failures.append("缺少 analysis_result.json")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="artifact",
                code="missing_result_json",
                message="未生成 analysis_result.json",
            )
        )
        score -= 0.35
    elif not Path(bundle.result_json_path).exists() or Path(bundle.result_json_path).stat().st_size == 0:
        hard_failures.append("analysis_result.json 不存在或为空")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="artifact",
                code="empty_result_json",
                message="analysis_result.json 不存在或为空",
            )
        )
        score -= 0.35

    schema_result = run_schema_checks(bundle.result_data, spec)
    findings.extend(schema_result.findings)
    hard_failures.extend(schema_result.hard_failures)
    score = max(0.0, min(score, schema_result.score))

    return CheckResult(
        score=max(0.0, min(score, 1.0)),
        hard_failures=hard_failures,
        findings=findings,
        metric_assertions=schema_result.metric_assertions,
    )
