"""数据分析工具

提供数据清洗、统计分析、数据转换等功能。
"""

from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from scipy import stats

from backend.tools.base import BaseTool, ToolError


class DataCleaningArgs(BaseModel):
    """数据清洗参数"""

    data: list[dict[str, Any]] = Field(..., description="要清洗的数据（字典列表）")
    operations: list[str] = Field(
        ...,
        description="清洗操作列表: drop_missing/fill_missing/drop_duplicates/remove_outliers",
    )
    fill_value: Any = Field(default=None, description="填充缺失值的值")
    fill_method: str = Field(
        default="constant", description="填充方法: constant/mean/median/mode"
    )
    outlier_method: str = Field(
        default="iqr", description="异常值检测方法: iqr/zscore"
    )
    outlier_threshold: float = Field(default=1.5, description="异常值阈值（IQR 方法）")
    columns: list[str] | None = Field(default=None, description="指定操作的列（默认所有列）")


class StatisticalAnalysisArgs(BaseModel):
    """统计分析参数"""

    data: list[dict[str, Any]] = Field(..., description="要分析的数据（字典列表）")
    analysis_type: str = Field(
        ...,
        description="分析类型: descriptive/correlation/hypothesis_test/normality",
    )
    columns: list[str] | None = Field(default=None, description="指定分析的列")
    group_by: str | None = Field(default=None, description="分组列名")
    test_type: str | None = Field(
        default=None, description="假设检验类型: ttest/anova/chi2"
    )


class DataTransformationArgs(BaseModel):
    """数据转换参数"""

    data: list[dict[str, Any]] = Field(..., description="要转换的数据（字典列表）")
    transformation: str = Field(
        ...,
        description="转换类型: normalize/standardize/log/one_hot/label_encode/binning",
    )
    columns: list[str] = Field(..., description="要转换的列")
    bins: int = Field(default=5, description="分箱数量（用于 binning）")
    labels: list[str] | None = Field(default=None, description="分箱标签")


class DataCleaningTool(BaseTool):
    """数据清洗工具

    支持缺失值处理、重复值删除、异常值检测等功能。
    """

    @property
    def name(self) -> str:
        return "data_cleaning"

    @property
    def description(self) -> str:
        return "数据清洗：处理缺失值、重复值、异常值等"

    @property
    def capability(self) -> str:
        return "执行数据清洗操作，包括删除/填充缺失值、删除重复值、移除异常值（IQR/Z-score 方法）"

    @property
    def limitations(self) -> list[str]:
        return [
            "不支持复杂的数据清洗规则",
            "异常值检测仅支持 IQR 和 Z-score 方法",
            "填充方法有限，不支持插值"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "数据预处理阶段",
            "处理公共卫生监测数据中的缺失值",
            "清理重复记录",
            "识别和处理异常值"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return DataCleaningArgs

    def _drop_missing(self, df: pd.DataFrame, columns: list[str] | None) -> pd.DataFrame:
        """删除缺失值"""
        subset = columns if columns else None
        return df.dropna(subset=subset)

    def _fill_missing(
        self,
        df: pd.DataFrame,
        columns: list[str] | None,
        fill_value: Any,
        fill_method: str,
    ) -> pd.DataFrame:
        """填充缺失值"""
        target_cols = columns if columns else df.columns.tolist()

        for col in target_cols:
            if col not in df.columns:
                continue

            if fill_method == "constant":
                df[col] = df[col].fillna(fill_value)
            elif fill_method == "mean":
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean())
            elif fill_method == "median":
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].median())
            elif fill_method == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val.iloc[0])

        return df

    def _drop_duplicates(
        self, df: pd.DataFrame, columns: list[str] | None
    ) -> pd.DataFrame:
        """删除重复值"""
        subset = columns if columns else None
        return df.drop_duplicates(subset=subset)

    def _remove_outliers(
        self,
        df: pd.DataFrame,
        columns: list[str] | None,
        method: str,
        threshold: float,
    ) -> pd.DataFrame:
        """移除异常值"""
        target_cols = columns if columns else df.select_dtypes(include=[np.number]).columns.tolist()

        for col in target_cols:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue

            if method == "iqr":
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr
                df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
            elif method == "zscore":
                z_scores = np.abs(stats.zscore(df[col].dropna()))
                df = df[z_scores <= threshold]

        return df

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = DataCleaningArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)
            original_shape = df.shape

            for operation in args.operations:
                if operation == "drop_missing":
                    df = self._drop_missing(df, args.columns)
                elif operation == "fill_missing":
                    df = self._fill_missing(
                        df, args.columns, args.fill_value, args.fill_method
                    )
                elif operation == "drop_duplicates":
                    df = self._drop_duplicates(df, args.columns)
                elif operation == "remove_outliers":
                    df = self._remove_outliers(
                        df, args.columns, args.outlier_method, args.outlier_threshold
                    )
                else:
                    raise ToolError(f"未知的清洗操作: {operation}")

            return {
                "original_shape": {"rows": original_shape[0], "columns": original_shape[1]},
                "cleaned_shape": {"rows": len(df), "columns": len(df.columns)},
                "rows_removed": original_shape[0] - len(df),
                "operations_performed": args.operations,
                "cleaned_data": df.to_dict(orient="records"),
            }
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"数据清洗失败: {e}") from e


class StatisticalAnalysisTool(BaseTool):
    """统计分析工具

    支持描述性统计、相关性分析、假设检验等功能。
    """

    @property
    def name(self) -> str:
        return "statistical_analysis"

    @property
    def description(self) -> str:
        return "统计分析：描述性统计、相关性分析、假设检验等"

    @property
    def capability(self) -> str:
        return "执行基础统计分析，包括描述性统计、相关性分析、假设检验（t检验/ANOVA/卡方）、正态性检验"

    @property
    def limitations(self) -> list[str]:
        return [
            "仅支持基础统计检验",
            "不支持非参数检验",
            "不支持多变量方差分析",
            "假设检验需要满足前提条件（如正态性）"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "探索性数据分析",
            "组间差异比较",
            "变量相关性探索",
            "数据分布特征分析"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return StatisticalAnalysisArgs

    def _descriptive_stats(
        self, df: pd.DataFrame, columns: list[str] | None, group_by: str | None
    ) -> dict[str, Any]:
        """描述性统计"""
        target_cols = columns if columns else df.select_dtypes(include=[np.number]).columns.tolist()

        if group_by and group_by in df.columns:
            grouped = df.groupby(group_by)[target_cols]
            result = {}
            for name, group in grouped:
                result[str(name)] = group.describe().to_dict()
            return {"grouped_statistics": result}

        return {"statistics": df[target_cols].describe().to_dict()}

    def _correlation_analysis(
        self, df: pd.DataFrame, columns: list[str] | None
    ) -> dict[str, Any]:
        """相关性分析"""
        target_cols = columns if columns else df.select_dtypes(include=[np.number]).columns.tolist()
        corr_matrix = df[target_cols].corr()

        return {
            "correlation_matrix": corr_matrix.to_dict(),
            "strong_correlations": self._find_strong_correlations(corr_matrix),
        }

    def _find_strong_correlations(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """找出强相关变量对"""
        strong_corrs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                col1, col2 = corr_matrix.columns[i], corr_matrix.columns[j]
                corr_val = corr_matrix.iloc[i, j]
                if abs(corr_val) >= threshold:
                    strong_corrs.append(
                        {"var1": col1, "var2": col2, "correlation": float(corr_val)}
                    )
        return strong_corrs

    def _hypothesis_test(
        self,
        df: pd.DataFrame,
        test_type: str,
        columns: list[str] | None,
        group_by: str | None,
    ) -> dict[str, Any]:
        """假设检验"""
        if not columns or len(columns) < 1:
            raise ToolError("假设检验需要指定至少一个数值列")

        target_col = columns[0]

        if test_type == "ttest":
            if not group_by or group_by not in df.columns:
                raise ToolError("t 检验需要指定分组列")

            groups = df.groupby(group_by)[target_col]
            if len(groups) != 2:
                raise ToolError("t 检验需要恰好两个分组")

            group_data = [g for _, g in groups]
            stat, p_value = stats.ttest_ind(group_data[0], group_data[1])
            return {
                "test_type": "独立样本 t 检验",
                "statistic": float(stat),
                "p_value": float(p_value),
                "significant": p_value < 0.05,
            }

        elif test_type == "anova":
            if not group_by or group_by not in df.columns:
                raise ToolError("ANOVA 需要指定分组列")

            groups = [g for _, g in df.groupby(group_by)[target_col]]
            stat, p_value = stats.f_oneway(*groups)
            return {
                "test_type": "单因素方差分析",
                "statistic": float(stat),
                "p_value": float(p_value),
                "significant": p_value < 0.05,
            }

        elif test_type == "chi2":
            if len(columns) < 2:
                raise ToolError("卡方检验需要两个分类变量")

            contingency = pd.crosstab(df[columns[0]], df[columns[1]])
            stat, p_value, dof, expected = stats.chi2_contingency(contingency)
            return {
                "test_type": "卡方独立性检验",
                "statistic": float(stat),
                "p_value": float(p_value),
                "degrees_of_freedom": int(dof),
                "significant": p_value < 0.05,
            }

        raise ToolError(f"未知的假设检验类型: {test_type}")

    def _normality_test(
        self, df: pd.DataFrame, columns: list[str] | None
    ) -> dict[str, Any]:
        """正态性检验"""
        target_cols = columns if columns else df.select_dtypes(include=[np.number]).columns.tolist()

        results = {}
        for col in target_cols:
            if col not in df.columns:
                continue
            data = df[col].dropna()
            if len(data) < 3:
                continue

            stat, p_value = stats.shapiro(data)
            results[col] = {
                "statistic": float(stat),
                "p_value": float(p_value),
                "is_normal": p_value > 0.05,
            }

        return {"normality_tests": results}

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = StatisticalAnalysisArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)

            if args.analysis_type == "descriptive":
                return self._descriptive_stats(df, args.columns, args.group_by)
            elif args.analysis_type == "correlation":
                return self._correlation_analysis(df, args.columns)
            elif args.analysis_type == "hypothesis_test":
                if not args.test_type:
                    raise ToolError("假设检验需要指定 test_type 参数")
                return self._hypothesis_test(
                    df, args.test_type, args.columns, args.group_by
                )
            elif args.analysis_type == "normality":
                return self._normality_test(df, args.columns)
            else:
                raise ToolError(f"未知的分析类型: {args.analysis_type}")

        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"统计分析失败: {e}") from e


class DataTransformationTool(BaseTool):
    """数据转换工具

    支持标准化、归一化、编码、分箱等转换操作。
    """

    @property
    def name(self) -> str:
        return "data_transformation"

    @property
    def description(self) -> str:
        return "数据转换：标准化、归一化、编码、分箱等"

    @property
    def capability(self) -> str:
        return "执行数据转换操作，包括归一化、标准化、对数转换、独热编码、标签编码、分箱"

    @property
    def limitations(self) -> list[str]:
        return [
            "不支持自定义转换函数",
            "分箱仅支持等宽分箱",
            "编码后不保留原始映射关系"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "机器学习模型数据预处理",
            "特征工程",
            "数据标准化处理",
            "分类变量编码"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return DataTransformationArgs

    def _normalize(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """归一化（Min-Max 缩放到 [0, 1]）"""
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val != min_val:
                    df[col] = (df[col] - min_val) / (max_val - min_val)
        return df

    def _standardize(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """标准化（Z-score）"""
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                std_val = df[col].std()
                if std_val != 0:
                    df[col] = (df[col] - mean_val) / std_val
        return df

    def _log_transform(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """对数转换"""
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = df[col].min()
                if min_val <= 0:
                    df[col] = np.log1p(df[col] - min_val + 1)
                else:
                    df[col] = np.log(df[col])
        return df

    def _one_hot_encode(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """独热编码"""
        for col in columns:
            if col in df.columns:
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df.drop(col, axis=1), dummies], axis=1)
        return df

    def _label_encode(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        """标签编码"""
        for col in columns:
            if col in df.columns:
                df[col] = pd.Categorical(df[col]).codes
        return df

    def _binning(
        self, df: pd.DataFrame, columns: list[str], bins: int, labels: list[str] | None
    ) -> pd.DataFrame:
        """分箱"""
        for col in columns:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                df[f"{col}_binned"] = pd.cut(df[col], bins=bins, labels=labels)
        return df

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = DataTransformationArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)
            original_columns = list(df.columns)

            if args.transformation == "normalize":
                df = self._normalize(df, args.columns)
            elif args.transformation == "standardize":
                df = self._standardize(df, args.columns)
            elif args.transformation == "log":
                df = self._log_transform(df, args.columns)
            elif args.transformation == "one_hot":
                df = self._one_hot_encode(df, args.columns)
            elif args.transformation == "label_encode":
                df = self._label_encode(df, args.columns)
            elif args.transformation == "binning":
                df = self._binning(df, args.columns, args.bins, args.labels)
            else:
                raise ToolError(f"未知的转换类型: {args.transformation}")

            return {
                "transformation": args.transformation,
                "original_columns": original_columns,
                "transformed_columns": list(df.columns),
                "transformed_data": df.to_dict(orient="records"),
            }
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"数据转换失败: {e}") from e
