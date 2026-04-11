"""报告质量的轻量规则检查。"""

from __future__ import annotations

from backend.evaluation.schemas import ArtifactBundle, CheckResult, EvaluationFinding, TaskSpec


def run_report_checks(bundle: ArtifactBundle, spec: TaskSpec) -> CheckResult:
    """基于关键字检查报告完整度。"""
    if not bundle.report_text.strip():
        return CheckResult(
            score=0.0,
            hard_failures=["缺少报告内容，无法通过报告检查"],
            findings=[
                EvaluationFinding(
                    severity="error",
                    category="report",
                    code="empty_report_text",
                    message="缺少报告内容，无法通过报告检查",
                )
            ],
        )

    if not spec.report_keywords:
        return CheckResult(score=1.0)

    findings: list[EvaluationFinding] = []
    hit_count = 0
    report_text = bundle.report_text.lower()
    missing_keywords: list[str] = []

    for keyword in spec.report_keywords:
        if keyword.lower() in report_text:
            hit_count += 1
            continue
        missing_keywords.append(keyword)

    score = hit_count / max(len(spec.report_keywords), 1)
    if missing_keywords:
        findings.append(
            EvaluationFinding(
                severity="warning",
                category="report",
                code="missing_report_keywords",
                message=f"报告缺少部分关键说明: {', '.join(missing_keywords)}",
            )
        )

    return CheckResult(score=score, findings=findings)
