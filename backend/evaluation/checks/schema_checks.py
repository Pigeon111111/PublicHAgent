"""结构化结果 schema 检查。"""

from __future__ import annotations

from backend.evaluation.schemas import CheckResult, EvaluationFinding, TaskSpec


def run_schema_checks(result_data: dict[str, object], spec: TaskSpec) -> CheckResult:
    """检查结果 JSON 是否包含任务所需关键字段。"""
    if not spec.required_json_fields:
        return CheckResult(score=1.0)

    findings: list[EvaluationFinding] = []
    missing_fields: list[str] = []
    present_count = 0

    for field in spec.required_json_fields:
        if field in result_data:
            present_count += 1
            continue
        missing_fields.append(field)
        findings.append(
            EvaluationFinding(
                severity="error",
                category="schema",
                code="missing_json_field",
                message=f"结果 JSON 缺少字段: {field}",
            )
        )

    score = present_count / max(len(spec.required_json_fields), 1)
    return CheckResult(
        score=score,
        hard_failures=[f"结果 JSON 缺少关键字段: {', '.join(missing_fields)}"] if missing_fields else [],
        findings=findings,
    )
