"""评估层结构化数据定义。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationFinding(BaseModel):
    """单条评估发现。"""

    severity: Literal["info", "warning", "error"] = "info"
    category: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class MetricAssertion(BaseModel):
    """单条指标断言结果。"""

    metric: str
    expected: Any = None
    actual: Any = None
    passed: bool
    tolerance: str = ""


class CheckResult(BaseModel):
    """单个检查器的输出。"""

    supported: bool = True
    score: float = 0.0
    hard_failures: list[str] = Field(default_factory=list)
    findings: list[EvaluationFinding] = Field(default_factory=list)
    metric_assertions: list[MetricAssertion] = Field(default_factory=list)


class EvaluationScoreBreakdown(BaseModel):
    """分项评分。"""

    artifact_score: float = 0.0
    statistical_score: float = 0.0
    process_score: float = 0.0
    report_score: float = 0.0


class EvaluationReport(BaseModel):
    """完整评估报告。"""

    evaluator_version: str = "2026-04-v1"
    task_family: str = "general"
    passed: bool = False
    final_score: float = 0.0
    score_breakdown: EvaluationScoreBreakdown = Field(default_factory=EvaluationScoreBreakdown)
    supported_checks: list[str] = Field(default_factory=list)
    hard_failures: list[str] = Field(default_factory=list)
    findings: list[EvaluationFinding] = Field(default_factory=list)
    metric_assertions: list[MetricAssertion] = Field(default_factory=list)
    summary: str = ""
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class TaskSpec(BaseModel):
    """任务规格。"""

    family: str
    intents: list[str] = Field(default_factory=list)
    required_json_fields: list[str] = Field(default_factory=list)
    report_keywords: list[str] = Field(default_factory=list)
    statistical_mode: Literal["none", "descriptive", "regression", "survival"] = "none"


class ArtifactBundle(BaseModel):
    """评估器可见的产物集合。"""

    task_family: str = "general"
    input_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    report_path: str | None = None
    result_json_path: str | None = None
    report_text: str = ""
    result_data: dict[str, Any] = Field(default_factory=dict)
