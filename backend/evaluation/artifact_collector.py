"""收集评估所需产物。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.evaluation.schemas import ArtifactBundle


class ArtifactCollector:
    """从执行结果与工作区中收集产物。"""

    def collect(
        self,
        *,
        intent: str,
        executor_results: list[Any],
        workspace: dict[str, Any],
    ) -> ArtifactBundle:
        output_files: list[str] = []
        for result in executor_results:
            artifacts = getattr(result, "artifacts", {}) or {}
            output_files.extend(str(path) for path in artifacts.get("output_files", []))

        if not output_files:
            output_dir = Path(str(workspace.get("output_dir") or "")).expanduser()
            if output_dir.exists():
                output_files = [str(path.resolve()) for path in output_dir.rglob("*") if path.is_file()]

        report_path = next(
            (path for path in output_files if Path(path).name == "analysis_report.md"),
            None,
        )
        result_json_path = next(
            (path for path in output_files if Path(path).name == "analysis_result.json"),
            None,
        )

        report_text = ""
        if report_path is not None and Path(report_path).exists():
            report_text = Path(report_path).read_text(encoding="utf-8", errors="replace")

        result_data: dict[str, Any] = {}
        if result_json_path is not None and Path(result_json_path).exists():
            try:
                result_data = json.loads(Path(result_json_path).read_text(encoding="utf-8"))
            except Exception:
                result_data = {}

        return ArtifactBundle(
            task_family=intent or "general",
            input_files=[str(path) for path in workspace.get("input_files", [])],
            output_files=sorted(set(output_files)),
            report_path=report_path,
            result_json_path=result_json_path,
            report_text=report_text,
            result_data=result_data,
        )
