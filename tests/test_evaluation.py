"""评估层测试。"""

import json
from pathlib import Path

import pandas as pd

from backend.agents.executor.schemas import ExecutionResult
from backend.evaluation.checks.statistical_checks import (
    _compute_survival_summary,
    _fit_cox_ph,
    _fit_linear_regression,
    _fit_logistic_regression,
)
from backend.evaluation.orchestrator import EvaluationOrchestrator


def _build_descriptive_result(df: pd.DataFrame, input_file: Path, output_dir: Path) -> tuple[Path, Path]:
    result_data = {
        "analysis_method": "描述统计",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": [str(column) for column in df.columns],
        "missing_values": {str(column): int(df[column].isna().sum()) for column in df.columns},
        "descriptive_statistics": df.select_dtypes(include="number").describe().to_dict(),
    }
    report_path = output_dir / "analysis_report.md"
    result_path = output_dir / "analysis_result.json"
    report_path.write_text(
        "\n".join(
            [
                "# 数据分析报告",
                "",
                "分析方法: 描述统计",
                f"数据文件: {input_file.name}",
                "字段: a, b",
                "缺失值: 无",
            ]
        ),
        encoding="utf-8",
    )
    result_path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path, result_path


def test_evaluation_orchestrator_descriptive_success(tmp_path: Path) -> None:
    """描述统计任务应通过 artifact 和 statistical 校验。"""
    input_file = tmp_path / "input.csv"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [10.0, 12.0, 14.0, 16.0]})
    df.to_csv(input_file, index=False)
    report_path, result_path = _build_descriptive_result(df, input_file, output_dir)

    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="descriptive_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.task_family == "descriptive_analysis"
    assert report.passed is True
    assert report.final_score > 0.9
    assert report.score_breakdown.statistical_score > 0.95


def test_evaluation_orchestrator_missing_artifact(tmp_path: Path) -> None:
    """缺少核心产物时应直接失败。"""
    input_file = tmp_path / "input.csv"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    pd.DataFrame({"a": [1, 2, 3]}).to_csv(input_file, index=False)

    report_path = output_dir / "analysis_report.md"
    report_path.write_text("# 数据分析报告", encoding="utf-8")

    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="descriptive_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is False
    assert any("analysis_result.json" in item for item in report.hard_failures)


def _write_analysis_outputs(
    *,
    output_dir: Path,
    result_data: dict[str, object],
    report_lines: list[str],
) -> tuple[Path, Path]:
    report_path = output_dir / "analysis_report.md"
    result_path = output_dir / "analysis_result.json"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    result_path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path, result_path


def test_evaluation_orchestrator_regression_linear_success(tmp_path: Path) -> None:
    """线性回归结果应通过专用统计校验。"""
    input_file = tmp_path / "linear.csv"
    output_dir = tmp_path / "output_linear"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "x1": [1, 2, 3, 4, 5, 6, 7, 8],
            "x2": [2, 1, 0, 3, 1, 4, 2, 5],
            "y": [6.0, 7.0, 9.0, 12.0, 13.5, 17.0, 19.0, 22.5],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _fit_linear_regression(df, target="y", features=["x1", "x2"])
    result_data = {
        "analysis_method": "线性回归",
        "analysis_type": "regression_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "model_type": "linear",
        "target": "y",
        "features": ["x1", "x2"],
        "coefficients": reference["coefficients"],
        "p_values": reference["p_values"],
        "fit_metrics": reference["fit_metrics"],
        "confidence_intervals": reference["confidence_intervals"],
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: 线性回归",
            f"数据文件: {input_file.name}",
            "结果: 模型拟合完成",
            "结论: x1 和 x2 与 y 存在线性关系。",
        ],
    )

    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="regression_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.task_family == "regression_analysis"
    assert report.passed is True
    assert report.score_breakdown.statistical_score > 0.95


def test_evaluation_orchestrator_regression_logistic_success(tmp_path: Path) -> None:
    """Logistic 回归结果应通过专用统计校验。"""
    input_file = tmp_path / "logistic.csv"
    output_dir = tmp_path / "output_logistic"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "age": [31, 45, 28, 37, 52, 41, 33, 48, 29, 55, 39, 43],
            "marker": [0.4, 1.3, 0.2, 0.8, 1.8, 1.1, 0.5, 1.5, 0.3, 1.9, 0.9, 1.2],
            "event": [0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _fit_logistic_regression(df, target="event", features=["age", "marker"])
    result_data = {
        "analysis_method": "Logistic 回归",
        "analysis_type": "regression_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "model_type": "logistic",
        "target": "event",
        "features": ["age", "marker"],
        "coefficients": reference["coefficients"],
        "p_values": reference["p_values"],
        "fit_metrics": reference["fit_metrics"],
        "confidence_intervals": reference["confidence_intervals"],
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: Logistic 回归",
            f"数据文件: {input_file.name}",
            "结果: Logistic 模型拟合完成。",
            "结论: 年龄和 marker 与 event 发生概率相关。",
        ],
    )

    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="regression_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is True
    assert report.score_breakdown.statistical_score > 0.9


def test_evaluation_orchestrator_regression_failure_on_wrong_sign(tmp_path: Path) -> None:
    """系数方向错误时应触发硬失败。"""
    input_file = tmp_path / "linear_bad.csv"
    output_dir = tmp_path / "output_linear_bad"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "x1": [1, 2, 3, 4, 5, 6],
            "x2": [2, 4, 1, 5, 3, 7],
            "y": [2.0, 4.1, 5.9, 8.2, 10.1, 11.8],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _fit_linear_regression(df, target="y", features=["x1", "x2"])
    bad_coefficients = dict(reference["coefficients"])
    bad_coefficients["x1"] = -abs(float(bad_coefficients["x1"]))
    result_data = {
        "analysis_method": "线性回归",
        "analysis_type": "regression_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "model_type": "linear",
        "target": "y",
        "features": ["x1", "x2"],
        "coefficients": bad_coefficients,
        "p_values": reference["p_values"],
        "fit_metrics": reference["fit_metrics"],
        "confidence_intervals": reference["confidence_intervals"],
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: 线性回归",
            f"数据文件: {input_file.name}",
            "结果: 模型拟合完成。",
            "结论: x1 与 y 呈负相关。",
        ],
    )
    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="regression_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is False
    assert any("方向错误" in item for item in report.hard_failures)


def test_evaluation_orchestrator_survival_km_success(tmp_path: Path) -> None:
    """Kaplan-Meier 与 log-rank 结果应通过专用统计校验。"""
    input_file = tmp_path / "survival_km.csv"
    output_dir = tmp_path / "output_survival_km"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "time": [5, 6, 6, 7, 10, 12, 4, 8, 9, 11, 13, 15],
            "event": [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1],
            "group": ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "B"],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _compute_survival_summary(df, time_column="time", event_column="event", group_column="group")
    result_data = {
        "analysis_method": "Kaplan-Meier 生存分析",
        "analysis_type": "survival_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "time_column": "time",
        "event_column": "event",
        "group_column": "group",
        "km_summary": reference["km_summary"],
        "median_survival": reference["median_survival"],
        "log_rank": reference["log_rank"],
        "cox_summary": {"features": []},
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: Kaplan-Meier 生存分析",
            f"数据文件: {input_file.name}",
            "结果: 给出 Kaplan-Meier 曲线和 Log-rank 检验。",
            "结论: 两组的生存差异可由 Log-rank 检验解释。",
        ],
    )
    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="survival_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is True
    assert report.score_breakdown.statistical_score > 0.95


def test_evaluation_orchestrator_survival_cox_success(tmp_path: Path) -> None:
    """Cox 回归结果应通过专用统计校验。"""
    input_file = tmp_path / "survival_cox.csv"
    output_dir = tmp_path / "output_survival_cox"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "time": [4, 6, 8, 9, 10, 12, 5, 7, 11, 13, 14, 15],
            "event": [1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 0],
            "group": ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "B"],
            "age": [50, 62, 55, 61, 58, 65, 44, 46, 49, 51, 53, 48],
            "marker": [1.4, 1.6, 1.2, 1.7, 1.3, 1.8, 0.8, 0.9, 1.0, 1.1, 1.2, 0.7],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _compute_survival_summary(df, time_column="time", event_column="event", group_column="group")
    cox_reference = _fit_cox_ph(df, time_column="time", event_column="event", covariates=["age", "marker"])
    result_data = {
        "analysis_method": "Cox 生存分析",
        "analysis_type": "survival_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "time_column": "time",
        "event_column": "event",
        "group_column": "group",
        "km_summary": reference["km_summary"],
        "median_survival": reference["median_survival"],
        "log_rank": reference["log_rank"],
        "cox_summary": {
            "features": ["age", "marker"],
            **cox_reference,
        },
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: Cox 生存分析",
            f"数据文件: {input_file.name}",
            "结果: 已输出 Kaplan-Meier、Log-rank 和 Cox 模型结果。",
            "结论: age 和 marker 会影响风险比。",
        ],
    )
    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="survival_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is True
    assert report.score_breakdown.statistical_score > 0.9


def test_evaluation_orchestrator_survival_failure_on_hr_direction(tmp_path: Path) -> None:
    """Cox HR 方向颠倒时应触发硬失败。"""
    input_file = tmp_path / "survival_bad.csv"
    output_dir = tmp_path / "output_survival_bad"
    output_dir.mkdir()

    df = pd.DataFrame(
        {
            "time": [4, 6, 8, 10, 12, 14, 5, 7, 9, 11, 13, 15],
            "event": [1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
            "group": ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "B"],
            "age": [60, 63, 59, 66, 61, 65, 42, 47, 45, 50, 52, 46],
        }
    )
    df.to_csv(input_file, index=False)
    reference = _compute_survival_summary(df, time_column="time", event_column="event", group_column="group")
    cox_reference = _fit_cox_ph(df, time_column="time", event_column="event", covariates=["age"])
    bad_hr = dict(cox_reference["hazard_ratios"])
    bad_hr["age"] = 1 / float(bad_hr["age"])
    result_data = {
        "analysis_method": "Cox 生存分析",
        "analysis_type": "survival_analysis",
        "source_file": str(input_file),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "time_column": "time",
        "event_column": "event",
        "group_column": "group",
        "km_summary": reference["km_summary"],
        "median_survival": reference["median_survival"],
        "log_rank": reference["log_rank"],
        "cox_summary": {
            "features": ["age"],
            "hazard_ratios": bad_hr,
            "p_values": cox_reference["p_values"],
            "confidence_intervals": cox_reference["confidence_intervals"],
            "log_likelihood": cox_reference["log_likelihood"],
        },
        "sample_size": reference["sample_size"],
    }
    report_path, result_path = _write_analysis_outputs(
        output_dir=output_dir,
        result_data=result_data,
        report_lines=[
            "# 数据分析报告",
            "",
            "分析方法: Cox 生存分析",
            f"数据文件: {input_file.name}",
            "结果: 已输出 Cox 模型结果。",
            "结论: age 对风险比的方向为保护作用。",
        ],
    )
    execution_result = ExecutionResult(
        success=True,
        output="完成",
        code="print('ok')",
        artifacts={"output_files": [str(report_path), str(result_path)]},
    )
    report = EvaluationOrchestrator().evaluate(
        intent="survival_analysis",
        executor_results=[execution_result],
        workspace={"input_files": [str(input_file)], "output_dir": str(output_dir)},
    )

    assert report.passed is False
    assert any("HR 方向错误" in item for item in report.hard_failures)
