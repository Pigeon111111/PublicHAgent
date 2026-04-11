"""统一组织各类评估检查。"""

from __future__ import annotations

from typing import Any

from backend.evaluation.aggregator import ScoreAggregator
from backend.evaluation.artifact_collector import ArtifactCollector
from backend.evaluation.checks import (
    run_artifact_checks,
    run_process_checks,
    run_report_checks,
    run_statistical_checks,
)
from backend.evaluation.schemas import EvaluationReport
from backend.evaluation.task_registry import resolve_task_spec


class EvaluationOrchestrator:
    """调度 artifact / statistical / process / report 四层评估。"""

    def __init__(self) -> None:
        self._artifact_collector = ArtifactCollector()
        self._aggregator = ScoreAggregator()

    def evaluate(
        self,
        *,
        intent: str,
        executor_results: list[Any],
        workspace: dict[str, Any],
    ) -> EvaluationReport:
        """执行完整评估。"""
        spec = resolve_task_spec(intent)
        bundle = self._artifact_collector.collect(
            intent=spec.family,
            executor_results=executor_results,
            workspace=workspace,
        )

        artifact_result = run_artifact_checks(bundle, spec)
        statistical_result = run_statistical_checks(bundle, spec)
        process_result = run_process_checks(executor_results)
        report_result = run_report_checks(bundle, spec)

        artifact_paths = {
            "report_path": bundle.report_path or "",
            "result_json_path": bundle.result_json_path or "",
        }
        return self._aggregator.aggregate(
            task_family=spec.family,
            artifact=artifact_result,
            statistical=statistical_result,
            process=process_result,
            report=report_result,
            artifact_paths=artifact_paths,
        )
