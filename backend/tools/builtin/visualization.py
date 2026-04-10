"""数据可视化工具

提供基于 matplotlib/seaborn 的图表生成功能。
"""

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pydantic import BaseModel, Field

from backend.tools.base import BaseTool, ToolError

matplotlib.use("Agg")
sns.set_theme(style="whitegrid")


class PlottingArgs(BaseModel):
    """绑图参数"""

    data: list[dict[str, Any]] = Field(..., description="要绑图的数据（字典列表）")
    chart_type: str = Field(
        ...,
        description="图表类型: line/bar/scatter/histogram/box/violin/heatmap/pie/area",
    )
    x_column: str | None = Field(default=None, description="X 轴列名")
    y_column: str | list[str] | None = Field(default=None, description="Y 轴列名或列名列表")
    title: str = Field(default="", description="图表标题")
    x_label: str | None = Field(default=None, description="X 轴标签")
    y_label: str | None = Field(default=None, description="Y 轴标签")
    color: str | None = Field(default=None, description="颜色")
    hue: str | None = Field(default=None, description="分组颜色映射列")
    output_format: str = Field(default="base64", description="输出格式: base64/file")
    output_path: str | None = Field(default=None, description="输出文件路径（当 output_format 为 file 时）")
    figsize: tuple[float, float] = Field(default=(10.0, 6.0), description="图表尺寸（宽，高）")
    dpi: int = Field(default=100, description="分辨率")


class ChartGenerationArgs(BaseModel):
    """图表生成参数"""

    data: list[dict[str, Any]] = Field(..., description="要绑图的数据（字典列表）")
    chart_type: str = Field(
        ...,
        description="图表类型: correlation_matrix/distribution/comparison/timeseries",
    )
    columns: list[str] | None = Field(default=None, description="指定分析的列")
    group_by: str | None = Field(default=None, description="分组列")
    title: str = Field(default="", description="图表标题")
    output_format: str = Field(default="base64", description="输出格式: base64/file")
    output_path: str | None = Field(default=None, description="输出文件路径")
    figsize: tuple[float, float] = Field(default=(12.0, 8.0), description="图表尺寸")


class PlottingTool(BaseTool):
    """绑图工具

    支持多种常见图表类型的绑制。
    """

    @property
    def name(self) -> str:
        return "plotting"

    @property
    def description(self) -> str:
        return "绑制数据图表：折线图、柱状图、散点图、直方图等"

    @property
    def capability(self) -> str:
        return "绑制基础统计图表，包括折线图、柱状图、散点图、直方图、箱线图、小提琴图、热力图、饼图、面积图"

    @property
    def limitations(self) -> list[str]:
        return [
            "不支持 3D 图表",
            "不支持交互式图表",
            "图表样式定制能力有限",
            "输出为静态图片格式"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "数据分布可视化",
            "变量关系探索",
            "趋势分析展示",
            "公共卫生数据初步可视化"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return PlottingArgs

    def _save_figure(self, fig: plt.Figure, output_format: str, output_path: str | None) -> str:
        """保存图表"""
        if output_format == "base64":
            buffer = BytesIO()
            fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            plt.close(fig)
            return f"data:image/png;base64,{img_base64}"
        elif output_format == "file" and output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return f"图表已保存到: {output_path}"
        else:
            plt.close(fig)
            raise ToolError("文件输出需要指定 output_path")

    def _plot_line(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """折线图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        if args.hue and args.hue in df.columns:
            for name, group in df.groupby(args.hue):
                y_col = args.y_column
                if isinstance(y_col, list):
                    y_col = y_col[0]
                ax.plot(group[args.x_column], group[y_col], label=name)
            ax.legend()
        else:
            y_cols: list[str] = []
            if args.y_column:
                y_cols = [args.y_column] if isinstance(args.y_column, str) else args.y_column
            for y_col in y_cols:
                ax.plot(df[args.x_column], df[y_col], label=y_col)
            if y_cols and len(y_cols) > 1:
                ax.legend()

        return fig, ax

    def _plot_bar(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """柱状图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        if args.hue and args.hue in df.columns:
            sns.barplot(data=df, x=args.x_column, y=args.y_column, hue=args.hue, ax=ax)
        else:
            df.plot.bar(x=args.x_column, y=args.y_column, ax=ax, color=args.color)

        return fig, ax

    def _plot_scatter(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """散点图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        if args.hue and args.hue in df.columns:
            sns.scatterplot(data=df, x=args.x_column, y=args.y_column, hue=args.hue, ax=ax)
        else:
            ax.scatter(df[args.x_column], df[args.y_column], c=args.color)

        return fig, ax

    def _plot_histogram(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """直方图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        col = args.x_column or args.y_column
        if isinstance(col, list):
            col = col[0]

        if args.hue and args.hue in df.columns:
            for name, group in df.groupby(args.hue):
                ax.hist(group[col], alpha=0.6, label=name, bins=30)
            ax.legend()
        else:
            ax.hist(df[col], bins=30, color=args.color)

        return fig, ax

    def _plot_box(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """箱线图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        if args.x_column and args.y_column:
            sns.boxplot(data=df, x=args.x_column, y=args.y_column, hue=args.hue, ax=ax)
        else:
            col = args.y_column or args.x_column
            if isinstance(col, list):
                col = col[0]
            sns.boxplot(data=df, y=col, ax=ax)

        return fig, ax

    def _plot_violin(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """小提琴图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        if args.x_column and args.y_column:
            sns.violinplot(data=df, x=args.x_column, y=args.y_column, hue=args.hue, ax=ax)
        else:
            col = args.y_column or args.x_column
            if isinstance(col, list):
                col = col[0]
            sns.violinplot(data=df, y=col, ax=ax)

        return fig, ax

    def _plot_heatmap(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """热力图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        numeric_df = df.select_dtypes(include=["number"])

        sns.heatmap(numeric_df.corr(), annot=True, cmap="coolwarm", center=0, ax=ax)

        return fig, ax

    def _plot_pie(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """饼图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        col = args.x_column or args.y_column
        if isinstance(col, list):
            col = col[0]

        counts = df[col].value_counts()
        ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")

        return fig, ax

    def _plot_area(self, df: pd.DataFrame, args: PlottingArgs) -> tuple[plt.Figure, plt.Axes]:
        """面积图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        y_cols: list[str] | None = None
        if args.y_column:
            y_cols = [args.y_column] if isinstance(args.y_column, str) else args.y_column
        df.plot.area(x=args.x_column, y=y_cols, ax=ax, alpha=0.6)

        return fig, ax

    def run(self, **kwargs: Any) -> str:
        args = PlottingArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)

            plot_methods = {
                "line": self._plot_line,
                "bar": self._plot_bar,
                "scatter": self._plot_scatter,
                "histogram": self._plot_histogram,
                "box": self._plot_box,
                "violin": self._plot_violin,
                "heatmap": self._plot_heatmap,
                "pie": self._plot_pie,
                "area": self._plot_area,
            }

            if args.chart_type not in plot_methods:
                raise ToolError(f"不支持的图表类型: {args.chart_type}")

            fig, ax = plot_methods[args.chart_type](df, args)

            if args.title:
                ax.set_title(args.title)
            if args.x_label:
                ax.set_xlabel(args.x_label)
            if args.y_label:
                ax.set_ylabel(args.y_label)

            plt.tight_layout()

            return self._save_figure(fig, args.output_format, args.output_path)

        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"绑图失败: {e}") from e


class ChartGenerationTool(BaseTool):
    """图表生成工具

    提供高级图表生成功能，自动处理数据并生成专业图表。
    """

    @property
    def name(self) -> str:
        return "chart_generation"

    @property
    def description(self) -> str:
        return "生成高级分析图表：相关性矩阵、分布图、对比图、时序图等"

    @property
    def capability(self) -> str:
        return "生成高级分析图表，包括相关性矩阵热力图、多变量分布图、分组对比图、时序趋势图"

    @property
    def limitations(self) -> list[str]:
        return [
            "需要足够的数据量才能生成有意义的图表",
            "相关性矩阵仅支持数值型变量",
            "对比图需要指定分组变量",
            "时序图需要数据按时间排序"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "多变量相关性分析",
            "数据分布特征探索",
            "组间差异比较",
            "时间趋势分析"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return ChartGenerationArgs

    def _save_figure(self, fig: plt.Figure, output_format: str, output_path: str | None) -> str:
        """保存图表"""
        if output_format == "base64":
            buffer = BytesIO()
            fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            plt.close(fig)
            return f"data:image/png;base64,{img_base64}"
        elif output_format == "file" and output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            return f"图表已保存到: {output_path}"
        else:
            plt.close(fig)
            raise ToolError("文件输出需要指定 output_path")

    def _correlation_matrix(self, df: pd.DataFrame, args: ChartGenerationArgs) -> plt.Figure:
        """相关性矩阵热力图"""
        fig, ax = plt.subplots(figsize=args.figsize)

        numeric_df = df.select_dtypes(include=["number"])
        if args.columns:
            numeric_df = numeric_df[args.columns]

        corr = numeric_df.corr()
        mask = None

        sns.heatmap(
            corr,
            mask=mask,
            annot=True,
            cmap="RdBu_r",
            center=0,
            square=True,
            linewidths=0.5,
            ax=ax,
        )

        if args.title:
            ax.set_title(args.title)
        else:
            ax.set_title("变量相关性矩阵")

        return fig

    def _distribution(self, df: pd.DataFrame, args: ChartGenerationArgs) -> plt.Figure:
        """分布图"""
        target_cols = args.columns or df.select_dtypes(include=["number"]).columns.tolist()
        n_cols = min(len(target_cols), 3)
        n_rows = (len(target_cols) + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=args.figsize)

        if n_rows == 1 and n_cols == 1:
            axes_arr = [[axes]]
        elif n_rows == 1:
            axes_arr = [list(axes)]
        elif n_cols == 1:
            axes_arr = [[ax] for ax in axes]
        else:
            axes_arr = axes

        for idx, col in enumerate(target_cols):
            row, col_idx = idx // n_cols, idx % n_cols
            ax = axes_arr[row][col_idx]

            if args.group_by and args.group_by in df.columns:
                for name, group in df.groupby(args.group_by):
                    sns.kdeplot(data=group[col], label=name, ax=ax)
                ax.legend()
            else:
                sns.histplot(data=df, x=col, kde=True, ax=ax)

            ax.set_title(f"{col} 分布")

        for idx in range(len(target_cols), n_rows * n_cols):
            row, col_idx = idx // n_cols, idx % n_cols
            axes_arr[row][col_idx].set_visible(False)

        if args.title:
            fig.suptitle(args.title)

        return fig

    def _comparison(self, df: pd.DataFrame, args: ChartGenerationArgs) -> plt.Figure:
        """对比图"""
        if not args.group_by:
            raise ToolError("对比图需要指定 group_by 参数")

        target_cols = args.columns or df.select_dtypes(include=["number"]).columns.tolist()
        n_cols = min(len(target_cols), 2)
        n_rows = (len(target_cols) + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=args.figsize)
        if n_rows == 1 and n_cols == 1:
            axes = [[axes]]
        elif n_rows == 1:
            axes = axes.reshape(1, n_cols)
        elif n_cols == 1:
            axes = axes.reshape(n_rows, 1)

        for idx, col in enumerate(target_cols):
            row, col_idx = idx // n_cols, idx % n_cols
            ax = axes[row][col_idx]

            sns.boxplot(data=df, x=args.group_by, y=col, ax=ax)
            ax.set_title(f"{col} 按 {args.group_by} 分组对比")

        for idx in range(len(target_cols), n_rows * n_cols):
            row, col_idx = idx // n_cols, idx % n_cols
            axes[row][col_idx].set_visible(False)

        if args.title:
            fig.suptitle(args.title)

        return fig

    def _timeseries(self, df: pd.DataFrame, args: ChartGenerationArgs) -> plt.Figure:
        """时序图"""
        target_cols = args.columns or df.select_dtypes(include=["number"]).columns.tolist()

        fig, ax = plt.subplots(figsize=args.figsize)

        for col in target_cols:
            ax.plot(df.index, df[col], label=col, marker="o", markersize=3)

        ax.legend()
        ax.set_xlabel("时间")

        if args.title:
            ax.set_title(args.title)
        else:
            ax.set_title("时序趋势图")

        return fig

    def run(self, **kwargs: Any) -> str:
        args = ChartGenerationArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)

            chart_methods = {
                "correlation_matrix": self._correlation_matrix,
                "distribution": self._distribution,
                "comparison": self._comparison,
                "timeseries": self._timeseries,
            }

            if args.chart_type not in chart_methods:
                raise ToolError(f"不支持的图表类型: {args.chart_type}")

            fig = chart_methods[args.chart_type](df, args)

            plt.tight_layout()

            return self._save_figure(fig, args.output_format, args.output_path)

        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"图表生成失败: {e}") from e
