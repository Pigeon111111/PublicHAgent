"""聚合各检查器结果。"""

from __future__ import annotations

from backend.evaluation.schemas import CheckResult, EvaluationReport, EvaluationScoreBreakdown


class ScoreAggregator:
    """按权重聚合评分并生成最终评估报告。"""

    WEIGHTS = {
        "artifact": 0.2,
        "statistical": 0.45,
        "process": 0.2,
        "report": 0.15,
    }

    def aggregate(
        self,
        *,
        task_family: str,
        artifact: CheckResult,
        statistical: CheckResult,
        process: CheckResult,
        report: CheckResult,
        artifact_paths: dict[str, str],
    ) -> EvaluationReport:
        results = {
            "artifact": artifact,
            "statistical": statistical,
            "process": process,
            "report": report,
        }

        total_weight = 0.0
        total_score = 0.0
        supported_checks: list[str] = []
        hard_failures: list[str] = []
        findings = []
        metric_assertions = []

        for name, result in results.items():
            if result.supported:
                supported_checks.append(name)
                weight = self.WEIGHTS[name]
                total_weight += weight
                total_score += max(0.0, min(result.score, 1.0)) * weight
            hard_failures.extend(result.hard_failures)
            findings.extend(result.findings)
            metric_assertions.extend(result.metric_assertions)

        final_score = 0.0 if total_weight == 0 else round(total_score / total_weight, 4)
        passed = not hard_failures
        summary = "评估通过" if passed else f"评估失败: {'; '.join(hard_failures[:5])}"

        return EvaluationReport(
            task_family=task_family,
            passed=passed,
            final_score=final_score,
            score_breakdown=EvaluationScoreBreakdown(
                artifact_score=artifact.score,
                statistical_score=statistical.score,
                process_score=process.score,
                report_score=report.score,
            ),
            supported_checks=supported_checks,
            hard_failures=hard_failures,
            findings=findings,
            metric_assertions=metric_assertions,
            summary=summary,
            artifact_paths=artifact_paths,
        )
