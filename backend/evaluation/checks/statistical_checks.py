"""统计正确性检查。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize, stats

from backend.evaluation.schemas import (
    ArtifactBundle,
    CheckResult,
    EvaluationFinding,
    MetricAssertion,
    TaskSpec,
)


def _load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".feather":
        return pd.read_feather(path)
    raise ValueError(f"不支持的数据文件格式: {suffix}")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _compare_numeric(
    metric: str,
    expected: Any,
    actual: Any,
    *,
    rel_tol: float = 1e-4,
    abs_tol: float = 1e-6,
) -> MetricAssertion:
    expected_value = _safe_float(expected)
    actual_value = _safe_float(actual)
    if expected_value is None and actual_value is None:
        return MetricAssertion(metric=metric, expected=expected, actual=actual, passed=True, tolerance="none")

    passed = (
        expected_value is not None
        and actual_value is not None
        and math.isclose(expected_value, actual_value, rel_tol=rel_tol, abs_tol=abs_tol)
    )
    return MetricAssertion(
        metric=metric,
        expected=expected_value if expected_value is not None else expected,
        actual=actual_value if actual_value is not None else actual,
        passed=passed,
        tolerance=f"rel_tol={rel_tol}, abs_tol={abs_tol}",
    )


def _build_scored_result(
    *,
    metric_assertions: list[MetricAssertion],
    hard_failures: list[str],
    findings: list[EvaluationFinding],
    low_score_code: str,
    low_score_message: str,
    failure_message: str,
) -> CheckResult:
    passed_count = sum(1 for item in metric_assertions if item.passed)
    score = 0.0 if not metric_assertions else passed_count / len(metric_assertions)

    if score < 0.95:
        findings.append(
            EvaluationFinding(
                severity="warning" if score >= 0.8 else "error",
                category="statistical",
                code=low_score_code,
                message=f"{low_score_message}，当前得分 {score:.2f}",
            )
        )

    if score < 0.8 and not hard_failures:
        hard_failures.append(failure_message)

    return CheckResult(
        score=score,
        hard_failures=hard_failures,
        findings=findings,
        metric_assertions=metric_assertions,
    )


def _run_descriptive_checks(bundle: ArtifactBundle) -> CheckResult:
    if not bundle.input_files:
        return CheckResult(
            score=0.0,
            hard_failures=["缺少输入数据文件，无法执行描述统计校验"],
            findings=[
                EvaluationFinding(
                    severity="error",
                    category="statistical",
                    code="missing_input_files",
                    message="缺少输入数据文件，无法执行描述统计校验",
                )
            ],
        )

    result_data = bundle.result_data
    if not result_data:
        return CheckResult(
            score=0.0,
            hard_failures=["analysis_result.json 不是有效 JSON，无法执行统计校验"],
        )

    frame = _load_dataframe(bundle.input_files[0])
    numeric_df = frame.select_dtypes(include=[np.number])
    findings: list[EvaluationFinding] = []
    metric_assertions: list[MetricAssertion] = []
    hard_failures: list[str] = []

    shape_data = result_data.get("shape", {})
    metric_assertions.append(_compare_numeric("shape.rows", frame.shape[0], getattr(shape_data, "get", lambda *_: None)("rows")))
    metric_assertions.append(_compare_numeric("shape.columns", frame.shape[1], getattr(shape_data, "get", lambda *_: None)("columns")))

    missing_values = result_data.get("missing_values", {})
    for column in frame.columns:
        metric_assertions.append(
            _compare_numeric(
                f"missing_values.{column}",
                int(frame[column].isna().sum()),
                getattr(missing_values, "get", lambda *_: None)(str(column)),
            )
        )

    descriptive_statistics = result_data.get("descriptive_statistics")
    if not numeric_df.empty and not isinstance(descriptive_statistics, dict):
        hard_failures.append("描述统计任务缺少 descriptive_statistics 字段")
        findings.append(
            EvaluationFinding(
                severity="error",
                category="statistical",
                code="missing_descriptive_statistics",
                message="描述统计任务缺少 descriptive_statistics 字段",
            )
        )
    elif isinstance(descriptive_statistics, dict):
        description = numeric_df.describe().to_dict()
        for column, metrics in description.items():
            actual_metrics = descriptive_statistics.get(str(column), {})
            if not isinstance(actual_metrics, dict):
                hard_failures.append(f"描述统计列 {column} 的结果结构无效")
                continue
            for metric_name, expected_value in metrics.items():
                metric_assertions.append(
                    _compare_numeric(
                        f"descriptive_statistics.{column}.{metric_name}",
                        expected_value,
                        actual_metrics.get(metric_name),
                    )
                )

    return _build_scored_result(
        metric_assertions=metric_assertions,
        hard_failures=hard_failures,
        findings=findings,
        low_score_code="descriptive_score_low",
        low_score_message="描述统计指标一致性较低",
        failure_message="描述统计关键指标与参考计算不一致",
    )


def _run_regression_checks(bundle: ArtifactBundle) -> CheckResult:
    if not bundle.input_files:
        return CheckResult(score=0.0, hard_failures=["缺少输入数据文件，无法执行回归校验"])

    result_data = bundle.result_data or {}
    required_fields = [
        "model_type",
        "target",
        "features",
        "coefficients",
        "p_values",
        "fit_metrics",
        "confidence_intervals",
        "sample_size",
    ]
    missing_fields = [field for field in required_fields if field not in result_data]
    if missing_fields:
        return CheckResult(
            score=0.0,
            hard_failures=[f"缺少回归结果字段: {field}" for field in missing_fields],
        )

    frame = _load_dataframe(bundle.input_files[0])
    model_type = str(result_data.get("model_type", "")).strip().lower()
    target = str(result_data.get("target", "")).strip()
    features = [str(item) for item in result_data.get("features", [])]
    hard_failures: list[str] = []
    findings: list[EvaluationFinding] = []

    if model_type not in {"linear", "logistic"}:
        return CheckResult(
            score=0.0,
            hard_failures=[f"暂不支持的回归模型类型: {model_type}"],
            findings=[
                EvaluationFinding(
                    severity="error",
                    category="statistical",
                    code="unsupported_regression_model",
                    message=f"暂不支持的回归模型类型: {model_type}",
                )
            ],
        )

    if target not in frame.columns:
        hard_failures.append(f"回归目标列不存在: {target}")
    missing_features = [feature for feature in features if feature not in frame.columns]
    if missing_features:
        hard_failures.append(f"回归特征列不存在: {', '.join(missing_features)}")
    if hard_failures:
        return CheckResult(score=0.0, hard_failures=hard_failures)

    clean = frame[[target, *features]].dropna().copy()
    if clean.empty:
        return CheckResult(score=0.0, hard_failures=["回归输入数据在去除缺失值后为空"])

    reference = (
        _fit_linear_regression(clean, target=target, features=features)
        if model_type == "linear"
        else _fit_logistic_regression(clean, target=target, features=features)
    )

    metric_assertions = [_compare_numeric("sample_size", reference["sample_size"], result_data.get("sample_size"))]
    metric_assertions.extend(_compare_regression_metrics(result_data=result_data, reference=reference))
    hard_failures.extend(_check_regression_signs(result_data=result_data, reference=reference))
    findings.extend(_check_regression_report(bundle.report_text, model_type=model_type, target=target, features=features))

    return _build_scored_result(
        metric_assertions=metric_assertions,
        hard_failures=hard_failures,
        findings=findings,
        low_score_code="regression_score_low",
        low_score_message="回归关键指标与参考计算偏差较大",
        failure_message="回归关键指标与参考计算不一致",
    )


def _fit_linear_regression(frame: pd.DataFrame, *, target: str, features: list[str]) -> dict[str, Any]:
    y = frame[target].to_numpy(dtype=float)
    x = frame[features].to_numpy(dtype=float)
    x_design = np.column_stack([np.ones(len(frame)), x])
    coefficients, *_ = np.linalg.lstsq(x_design, y, rcond=None)
    predictions = x_design @ coefficients
    residuals = y - predictions
    n_obs = len(y)
    n_params = x_design.shape[1]
    sse = float(np.sum(residuals ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 0.0 if math.isclose(sst, 0.0) else 1.0 - (sse / sst)
    adj_r_squared = 1.0 - ((1.0 - r_squared) * (n_obs - 1) / max(n_obs - n_params, 1))
    sigma2 = sse / max(n_obs - n_params, 1)
    xtx_inv = np.linalg.inv(x_design.T @ x_design)
    standard_errors = np.sqrt(np.diag(sigma2 * xtx_inv))
    t_scores = coefficients / standard_errors
    p_values = 2 * (1 - stats.t.cdf(np.abs(t_scores), df=max(n_obs - n_params, 1)))
    critical = stats.t.ppf(0.975, df=max(n_obs - n_params, 1))
    ci_low = coefficients - critical * standard_errors
    ci_high = coefficients + critical * standard_errors
    labels = ["intercept", *features]
    return {
        "sample_size": n_obs,
        "coefficients": {label: float(value) for label, value in zip(labels, coefficients, strict=True)},
        "p_values": {label: float(value) for label, value in zip(labels, p_values, strict=True)},
        "confidence_intervals": {
            label: {"lower": float(lower), "upper": float(upper)}
            for label, lower, upper in zip(labels, ci_low, ci_high, strict=True)
        },
        "fit_metrics": {
            "r_squared": float(r_squared),
            "adjusted_r_squared": float(adj_r_squared),
        },
    }


def _fit_logistic_regression(frame: pd.DataFrame, *, target: str, features: list[str]) -> dict[str, Any]:
    y_raw = frame[target].to_numpy(dtype=float)
    unique_values = sorted(np.unique(y_raw))
    if set(unique_values) != {0.0, 1.0}:
        if len(unique_values) != 2:
            raise ValueError("Logistic 回归目标变量必须是二值变量")
        y = np.where(y_raw == unique_values[-1], 1.0, 0.0)
    else:
        y = y_raw

    x = frame[features].to_numpy(dtype=float)
    x_design = np.column_stack([np.ones(len(frame)), x])

    def sigmoid(value: np.ndarray) -> np.ndarray:
        return np.asarray(1.0 / (1.0 + np.exp(-np.clip(value, -50, 50))), dtype=float)

    def objective(beta: np.ndarray) -> float:
        logits = x_design @ beta
        probabilities = sigmoid(logits)
        eps = 1e-9
        return float(-np.sum(y * np.log(probabilities + eps) + (1 - y) * np.log(1 - probabilities + eps)))

    def gradient(beta: np.ndarray) -> np.ndarray:
        logits = x_design @ beta
        probabilities = sigmoid(logits)
        return np.asarray(x_design.T @ (probabilities - y), dtype=float)

    result = optimize.minimize(
        objective,
        np.zeros(x_design.shape[1], dtype=float),
        method="BFGS",
        jac=gradient,
        options={"maxiter": 300},
    )
    if not result.success:
        raise ValueError(f"Logistic 回归拟合失败: {result.message}")

    beta = result.x
    covariance = np.asarray(result.hess_inv)
    if covariance.ndim != 2:
        covariance = np.eye(len(beta))
    standard_errors = np.sqrt(np.clip(np.diag(covariance), 1e-12, None))
    z_scores = beta / standard_errors
    p_values = 2 * (1 - stats.norm.cdf(np.abs(z_scores)))
    ci_low = beta - 1.96 * standard_errors
    ci_high = beta + 1.96 * standard_errors
    logits = x_design @ beta
    probabilities = sigmoid(logits)
    auc = _binary_auc(y, probabilities)
    ll_model = -objective(beta)
    mean_y = float(np.clip(np.mean(y), 1e-9, 1 - 1e-9))
    ll_null = float(np.sum(y * np.log(mean_y) + (1 - y) * np.log(1 - mean_y)))
    mcfadden_r_squared = 0.0 if math.isclose(ll_null, 0.0) else 1.0 - (ll_model / ll_null)
    labels = ["intercept", *features]
    return {
        "sample_size": len(frame),
        "coefficients": {label: float(value) for label, value in zip(labels, beta, strict=True)},
        "p_values": {label: float(value) for label, value in zip(labels, p_values, strict=True)},
        "confidence_intervals": {
            label: {"lower": float(lower), "upper": float(upper)}
            for label, lower, upper in zip(labels, ci_low, ci_high, strict=True)
        },
        "fit_metrics": {
            "log_likelihood": float(ll_model),
            "mcfadden_r_squared": float(mcfadden_r_squared),
            "auc": float(auc),
        },
    }


def _binary_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    positives = scores[y_true == 1]
    negatives = scores[y_true == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return 0.0
    comparisons = 0.0
    for positive in positives:
        comparisons += float(np.sum(positive > negatives))
        comparisons += 0.5 * float(np.sum(positive == negatives))
    return comparisons / (len(positives) * len(negatives))


def _compare_regression_metrics(*, result_data: dict[str, Any], reference: dict[str, Any]) -> list[MetricAssertion]:
    assertions: list[MetricAssertion] = []
    coefficients = result_data.get("coefficients", {}) or {}
    for name, expected in reference["coefficients"].items():
        assertions.append(_compare_numeric(f"coefficients.{name}", expected, coefficients.get(name)))
    p_values = result_data.get("p_values", {}) or {}
    for name, expected in reference["p_values"].items():
        assertions.append(_compare_numeric(f"p_values.{name}", expected, p_values.get(name), rel_tol=5e-3, abs_tol=5e-3))
    intervals = result_data.get("confidence_intervals", {}) or {}
    for name, expected in reference["confidence_intervals"].items():
        actual = intervals.get(name) or {}
        assertions.append(_compare_numeric(f"confidence_intervals.{name}.lower", expected["lower"], actual.get("lower"), rel_tol=5e-3, abs_tol=5e-3))
        assertions.append(_compare_numeric(f"confidence_intervals.{name}.upper", expected["upper"], actual.get("upper"), rel_tol=5e-3, abs_tol=5e-3))
    fit_metrics = result_data.get("fit_metrics", {}) or {}
    for name, expected in reference["fit_metrics"].items():
        assertions.append(_compare_numeric(f"fit_metrics.{name}", expected, fit_metrics.get(name), rel_tol=5e-3, abs_tol=5e-3))
    return assertions


def _check_regression_signs(*, result_data: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    coefficients = result_data.get("coefficients", {}) or {}
    for name, expected in reference["coefficients"].items():
        if name == "intercept":
            continue
        actual = _safe_float(coefficients.get(name))
        if actual is None:
            continue
        if abs(expected) > 1e-6 and abs(actual) > 1e-6 and math.copysign(1, expected) != math.copysign(1, actual):
            failures.append(f"回归系数方向错误: {name}")
    return failures


def _check_regression_report(report_text: str, *, model_type: str, target: str, features: list[str]) -> list[EvaluationFinding]:
    findings: list[EvaluationFinding] = []
    report_lower = report_text.lower()
    if model_type not in report_lower and "回归" not in report_text:
        findings.append(EvaluationFinding(severity="warning", category="report", code="missing_regression_model_mention", message="报告中未明确说明回归模型类型"))
    if target and target.lower() not in report_lower:
        findings.append(EvaluationFinding(severity="warning", category="report", code="missing_regression_target", message=f"报告中未明确提及目标变量: {target}"))
    missing_features = [feature for feature in features if feature.lower() not in report_lower]
    if missing_features:
        findings.append(EvaluationFinding(severity="warning", category="report", code="missing_regression_features", message=f"报告中未明确提及部分特征变量: {', '.join(missing_features[:5])}"))
    return findings


def _run_survival_checks(bundle: ArtifactBundle) -> CheckResult:
    if not bundle.input_files:
        return CheckResult(score=0.0, hard_failures=["缺少输入数据文件，无法执行生存分析校验"])

    result_data = bundle.result_data or {}
    required_fields = [
        "time_column",
        "event_column",
        "group_column",
        "km_summary",
        "median_survival",
        "log_rank",
        "cox_summary",
        "sample_size",
    ]
    missing_fields = [field for field in required_fields if field not in result_data]
    if missing_fields:
        return CheckResult(score=0.0, hard_failures=[f"缺少生存分析结果字段: {field}" for field in missing_fields])

    frame = _load_dataframe(bundle.input_files[0])
    time_column = str(result_data.get("time_column", "")).strip()
    event_column = str(result_data.get("event_column", "")).strip()
    group_column = str(result_data.get("group_column", "")).strip()
    hard_failures: list[str] = []
    findings: list[EvaluationFinding] = []

    for column_name, label in ((time_column, "time"), (event_column, "event")):
        if column_name not in frame.columns:
            hard_failures.append(f"生存分析{label}列不存在: {column_name}")
    if group_column and group_column not in frame.columns:
        hard_failures.append(f"生存分析分组列不存在: {group_column}")
    if hard_failures:
        return CheckResult(score=0.0, hard_failures=hard_failures)

    covariates = [
        str(item)
        for item in (result_data.get("cox_summary", {}) or {}).get("features", [])
        if str(item) in frame.columns
    ]
    clean_columns = [time_column, event_column] + ([group_column] if group_column else []) + covariates
    clean = frame[clean_columns].dropna().copy()
    if clean.empty:
        return CheckResult(score=0.0, hard_failures=["生存分析输入数据在去除缺失值后为空"])

    unique_events = sorted(set(clean[event_column].astype(float).tolist()))
    if unique_events not in ([0.0, 1.0], [0.0], [1.0]):
        return CheckResult(score=0.0, hard_failures=["事件列不是标准 0/1 编码，无法通过生存分析硬校验"])

    reference_km = _compute_survival_summary(
        clean,
        time_column=time_column,
        event_column=event_column,
        group_column=group_column,
    )
    metric_assertions = [_compare_numeric("sample_size", reference_km["sample_size"], result_data.get("sample_size"))]
    metric_assertions.extend(_compare_survival_metrics(result_data=result_data, reference=reference_km))

    cox_result = result_data.get("cox_summary") or {}
    if covariates:
        reference_cox = _fit_cox_ph(
            clean,
            time_column=time_column,
            event_column=event_column,
            covariates=covariates,
        )
        metric_assertions.extend(_compare_cox_metrics(result_data=cox_result, reference=reference_cox))
        hard_failures.extend(_check_survival_signs(result_data=cox_result, reference=reference_cox))

    findings.extend(_check_survival_report(bundle.report_text, time_column=time_column, event_column=event_column, group_column=group_column))
    return _build_scored_result(
        metric_assertions=metric_assertions,
        hard_failures=hard_failures,
        findings=findings,
        low_score_code="survival_score_low",
        low_score_message="生存分析关键指标与参考计算偏差较大",
        failure_message="生存分析关键指标与参考计算不一致",
    )


def _compute_survival_summary(
    frame: pd.DataFrame,
    *,
    time_column: str,
    event_column: str,
    group_column: str,
) -> dict[str, Any]:
    grouped = {"overall": frame}
    if group_column:
        grouped = {str(name): group.copy() for name, group in frame.groupby(group_column)}

    km_summary: dict[str, Any] = {}
    median_survival: dict[str, Any] = {}
    for group_name, group in grouped.items():
        km = _kaplan_meier(group[time_column].to_numpy(dtype=float), group[event_column].to_numpy(dtype=float))
        km_summary[group_name] = {
            "events": km["events"],
            "censored": km["censored"],
            "survival_at_last_event": km["survival_at_last_event"],
        }
        median_survival[group_name] = km["median_survival"]

    log_rank = {"statistic": 0.0, "p_value": 1.0}
    if group_column and len(grouped) == 2:
        groups = list(grouped.values())
        log_rank = _log_rank_test(
            groups[0][time_column].to_numpy(dtype=float),
            groups[0][event_column].to_numpy(dtype=float),
            groups[1][time_column].to_numpy(dtype=float),
            groups[1][event_column].to_numpy(dtype=float),
        )

    return {
        "sample_size": len(frame),
        "km_summary": km_summary,
        "median_survival": median_survival,
        "log_rank": log_rank,
    }


def _kaplan_meier(time: np.ndarray, event: np.ndarray) -> dict[str, Any]:
    order = np.argsort(time)
    time = time[order]
    event = event[order]
    unique_event_times = sorted(np.unique(time[event == 1]))
    at_risk = len(time)
    survival = 1.0
    events = int(np.sum(event == 1))
    censored = int(np.sum(event == 0))
    median_survival: float | None = None

    for event_time in unique_event_times:
        event_count = int(np.sum((time == event_time) & (event == 1)))
        censored_count = int(np.sum((time == event_time) & (event == 0)))
        if at_risk > 0:
            survival *= 1.0 - (event_count / at_risk)
        if median_survival is None and survival <= 0.5:
            median_survival = float(event_time)
        at_risk -= event_count + censored_count

    return {
        "events": events,
        "censored": censored,
        "survival_at_last_event": float(survival),
        "median_survival": median_survival,
    }


def _log_rank_test(
    time_a: np.ndarray,
    event_a: np.ndarray,
    time_b: np.ndarray,
    event_b: np.ndarray,
) -> dict[str, Any]:
    event_times = sorted(np.unique(np.concatenate([time_a[event_a == 1], time_b[event_b == 1]])))
    observed = 0.0
    expected = 0.0
    variance = 0.0

    for event_time in event_times:
        risk_a = float(np.sum(time_a >= event_time))
        risk_b = float(np.sum(time_b >= event_time))
        events_a = float(np.sum((time_a == event_time) & (event_a == 1)))
        events_b = float(np.sum((time_b == event_time) & (event_b == 1)))
        total_risk = risk_a + risk_b
        total_events = events_a + events_b
        if total_risk <= 1 or total_events <= 0:
            continue
        observed += events_a
        expected += total_events * (risk_a / total_risk)
        variance += (risk_a * risk_b * total_events * (total_risk - total_events)) / (total_risk ** 2 * (total_risk - 1))

    statistic = 0.0 if variance <= 0 else (observed - expected) ** 2 / variance
    return {
        "statistic": float(statistic),
        "p_value": float(1 - stats.chi2.cdf(statistic, df=1)),
    }


def _fit_cox_ph(
    frame: pd.DataFrame,
    *,
    time_column: str,
    event_column: str,
    covariates: list[str],
) -> dict[str, Any]:
    times = frame[time_column].to_numpy(dtype=float)
    events = frame[event_column].to_numpy(dtype=float)
    x = frame[covariates].to_numpy(dtype=float)
    order = np.argsort(times)
    times = times[order]
    events = events[order]
    x = x[order]

    def objective(beta: np.ndarray) -> float:
        eta = x @ beta
        exp_eta = np.exp(np.clip(eta, -50, 50))
        total = 0.0
        for index, event_flag in enumerate(events):
            if event_flag != 1:
                continue
            risk_set = exp_eta[times >= times[index]]
            total -= eta[index] - math.log(float(np.sum(risk_set)))
        return float(total)

    def gradient(beta: np.ndarray) -> np.ndarray:
        eta = x @ beta
        exp_eta = np.exp(np.clip(eta, -50, 50))
        grad = np.zeros_like(beta)
        for index, event_flag in enumerate(events):
            if event_flag != 1:
                continue
            mask = times >= times[index]
            grad -= x[index] - (np.sum(x[mask] * exp_eta[mask, None], axis=0) / np.sum(exp_eta[mask]))
        return grad

    result = optimize.minimize(
        objective,
        np.zeros(len(covariates), dtype=float),
        method="BFGS",
        jac=gradient,
        options={"maxiter": 300},
    )
    if not result.success:
        raise ValueError(f"Cox 模型拟合失败: {result.message}")

    coefficients = result.x
    covariance = np.asarray(result.hess_inv)
    if covariance.ndim != 2:
        covariance = np.eye(len(coefficients))
    standard_errors = np.sqrt(np.clip(np.diag(covariance), 1e-12, None))
    z_scores = coefficients / standard_errors
    p_values = 2 * (1 - stats.norm.cdf(np.abs(z_scores)))
    hr = np.exp(coefficients)
    ci_low = np.exp(coefficients - 1.96 * standard_errors)
    ci_high = np.exp(coefficients + 1.96 * standard_errors)
    return {
        "hazard_ratios": {name: float(value) for name, value in zip(covariates, hr, strict=True)},
        "p_values": {name: float(value) for name, value in zip(covariates, p_values, strict=True)},
        "confidence_intervals": {
            name: {"lower": float(lower), "upper": float(upper)}
            for name, lower, upper in zip(covariates, ci_low, ci_high, strict=True)
        },
        "log_likelihood": float(-objective(coefficients)),
    }


def _compare_survival_metrics(*, result_data: dict[str, Any], reference: dict[str, Any]) -> list[MetricAssertion]:
    assertions: list[MetricAssertion] = []
    result_medians = result_data.get("median_survival", {}) or {}
    if not isinstance(result_medians, dict):
        result_medians = {"overall": result_medians}
    for group_name, expected in reference["median_survival"].items():
        assertions.append(_compare_numeric(f"median_survival.{group_name}", expected, result_medians.get(group_name), rel_tol=5e-3, abs_tol=5e-3))
    log_rank = result_data.get("log_rank", {}) or {}
    assertions.append(_compare_numeric("log_rank.statistic", reference["log_rank"]["statistic"], log_rank.get("statistic"), rel_tol=1e-3, abs_tol=1e-3))
    assertions.append(_compare_numeric("log_rank.p_value", reference["log_rank"]["p_value"], log_rank.get("p_value"), rel_tol=5e-3, abs_tol=5e-3))
    result_km = result_data.get("km_summary", {}) or {}
    for group_name, expected in reference["km_summary"].items():
        actual = result_km.get(group_name, {}) if isinstance(result_km, dict) else {}
        assertions.append(_compare_numeric(f"km_summary.{group_name}.events", expected["events"], actual.get("events")))
        assertions.append(_compare_numeric(f"km_summary.{group_name}.censored", expected["censored"], actual.get("censored")))
        assertions.append(_compare_numeric(f"km_summary.{group_name}.survival_at_last_event", expected["survival_at_last_event"], actual.get("survival_at_last_event"), rel_tol=5e-3, abs_tol=5e-3))
    return assertions


def _compare_cox_metrics(*, result_data: dict[str, Any], reference: dict[str, Any]) -> list[MetricAssertion]:
    assertions: list[MetricAssertion] = []
    hazard_ratios = result_data.get("hazard_ratios", {}) or {}
    p_values = result_data.get("p_values", {}) or {}
    intervals = result_data.get("confidence_intervals", {}) or {}
    for feature, expected in reference["hazard_ratios"].items():
        assertions.append(_compare_numeric(f"cox_summary.hazard_ratios.{feature}", expected, hazard_ratios.get(feature), rel_tol=5e-3, abs_tol=5e-3))
        assertions.append(_compare_numeric(f"cox_summary.p_values.{feature}", reference["p_values"][feature], p_values.get(feature), rel_tol=5e-3, abs_tol=5e-3))
        actual_interval = intervals.get(feature) or {}
        assertions.append(_compare_numeric(f"cox_summary.confidence_intervals.{feature}.lower", reference["confidence_intervals"][feature]["lower"], actual_interval.get("lower"), rel_tol=5e-3, abs_tol=5e-3))
        assertions.append(_compare_numeric(f"cox_summary.confidence_intervals.{feature}.upper", reference["confidence_intervals"][feature]["upper"], actual_interval.get("upper"), rel_tol=5e-3, abs_tol=5e-3))
    if "log_likelihood" in result_data:
        assertions.append(_compare_numeric("cox_summary.log_likelihood", reference["log_likelihood"], result_data.get("log_likelihood"), rel_tol=5e-3, abs_tol=5e-3))
    return assertions


def _check_survival_signs(*, result_data: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    hazard_ratios = result_data.get("hazard_ratios", {}) or {}
    for feature, expected in reference["hazard_ratios"].items():
        actual = _safe_float(hazard_ratios.get(feature))
        if actual is None:
            continue
        if expected > 1 and actual < 1:
            failures.append(f"Cox HR 方向错误: {feature}")
        if expected < 1 and actual > 1:
            failures.append(f"Cox HR 方向错误: {feature}")
    return failures


def _check_survival_report(report_text: str, *, time_column: str, event_column: str, group_column: str) -> list[EvaluationFinding]:
    findings: list[EvaluationFinding] = []
    report_lower = report_text.lower()
    for token, label in (("kaplan", "Kaplan-Meier / 生存曲线"), ("log-rank", "Log-rank 检验"), ("cox", "Cox 模型")):
        if token not in report_lower and label.split("/")[0] not in report_text:
            findings.append(EvaluationFinding(severity="warning", category="report", code=f"missing_survival_{token.replace('-', '_')}", message=f"报告中未明确说明 {label}"))
    for column_name, label in ((time_column, "时间列"), (event_column, "事件列"), (group_column, "分组列")):
        if column_name and column_name.lower() not in report_lower:
            findings.append(EvaluationFinding(severity="warning", category="report", code=f"missing_survival_column_{label}", message=f"报告中未明确提及{label}: {column_name}"))
    return findings


def run_statistical_checks(bundle: ArtifactBundle, spec: TaskSpec) -> CheckResult:
    if spec.statistical_mode == "descriptive":
        return _run_descriptive_checks(bundle)
    if spec.statistical_mode == "regression":
        return _run_regression_checks(bundle)
    if spec.statistical_mode == "survival":
        return _run_survival_checks(bundle)
    return CheckResult(
        supported=False,
        findings=[
            EvaluationFinding(
                severity="info",
                category="statistical",
                code="no_statistical_verifier",
                message="当前任务没有专用统计校验器，已跳过统计硬校验",
            )
        ],
    )
