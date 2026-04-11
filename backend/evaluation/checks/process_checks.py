"""过程质量检查。"""

from __future__ import annotations

from typing import Any

from backend.evaluation.schemas import CheckResult, EvaluationFinding


def run_process_checks(executor_results: list[Any]) -> CheckResult:
    """根据执行尝试次数、失败情况和反思结果评估过程质量。"""
    if not executor_results:
        return CheckResult(
            score=0.0,
            hard_failures=["没有执行结果，无法通过过程评估"],
            findings=[
                EvaluationFinding(
                    severity="error",
                    category="process",
                    code="missing_execution_results",
                    message="没有执行结果，无法通过过程评估",
                )
            ],
        )

    score = 1.0
    findings: list[EvaluationFinding] = []
    hard_failures: list[str] = []

    total_attempts = sum(max(int(getattr(result, "attempts", 1) or 1), 1) for result in executor_results)
    failed_results = [result for result in executor_results if not getattr(result, "success", False)]

    retry_penalty = max(total_attempts - len(executor_results), 0) * 0.08
    failure_penalty = len(failed_results) * 0.25
    score = max(0.0, 1.0 - retry_penalty - failure_penalty)

    if total_attempts > len(executor_results):
        findings.append(
            EvaluationFinding(
                severity="warning",
                category="process",
                code="retries_detected",
                message=f"检测到多次代码重试，总尝试次数 {total_attempts}",
            )
        )

    if failed_results:
        hard_failures.append(f"存在 {len(failed_results)} 个执行步骤最终失败")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="process",
                code="failed_steps",
                message=f"存在 {len(failed_results)} 个执行步骤最终失败",
            )
        )

    return CheckResult(score=score, hard_failures=hard_failures, findings=findings)
