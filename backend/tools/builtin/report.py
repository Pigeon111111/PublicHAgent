"""报告生成工具

提供 Markdown 和 HTML 格式的报告生成功能。
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from backend.tools.base import BaseTool, ToolError


class ReportSection(BaseModel):
    """报告章节"""

    title: str = Field(..., description="章节标题")
    content: str = Field(default="", description="章节内容（Markdown 格式）")
    level: int = Field(default=2, description="标题级别（1-6）")


class ReportGenerationArgs(BaseModel):
    """报告生成参数"""

    title: str = Field(..., description="报告标题")
    sections: list[ReportSection] = Field(default_factory=list, description="报告章节列表")
    format: str = Field(default="markdown", description="输出格式: markdown/html")
    output_path: str | None = Field(default=None, description="输出文件路径")
    include_toc: bool = Field(default=True, description="是否包含目录")
    include_timestamp: bool = Field(default=True, description="是否包含时间戳")
    author: str | None = Field(default=None, description="作者")
    data_summary: dict[str, Any] | None = Field(default=None, description="数据摘要（自动生成章节）")


class DataReportArgs(BaseModel):
    """数据报告参数"""

    data: list[dict[str, Any]] = Field(..., description="数据（字典列表）")
    title: str = Field(default="数据分析报告", description="报告标题")
    format: str = Field(default="markdown", description="输出格式: markdown/html")
    output_path: str | None = Field(default=None, description="输出文件路径")
    include_statistics: bool = Field(default=True, description="是否包含统计信息")
    include_missing_analysis: bool = Field(default=True, description="是否包含缺失值分析")
    include_distribution: bool = Field(default=True, description="是否包含分布分析")


class ReportGenerationTool(BaseTool):
    """报告生成工具

    支持 Markdown 和 HTML 格式的报告生成。
    """

    @property
    def name(self) -> str:
        return "report_generation"

    @property
    def description(self) -> str:
        return "生成 Markdown 或 HTML 格式的报告"

    @property
    def capability(self) -> str:
        return "生成结构化的分析报告，支持 Markdown 和 HTML 格式，可包含目录、章节、数据摘要"

    @property
    def limitations(self) -> list[str]:
        return [
            "不支持 PDF 格式输出",
            "不支持复杂的表格格式",
            "HTML 样式定制能力有限"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "生成数据分析报告",
            "创建研究文档",
            "导出分析结果摘要"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return ReportGenerationArgs

    def _generate_toc(self, sections: list[ReportSection]) -> str:
        """生成目录"""
        toc_lines = ["## 目录\n"]
        for idx, section in enumerate(sections, 1):
            indent = "  " * (section.level - 1)
            anchor = section.title.lower().replace(" ", "-")
            toc_lines.append(f"{indent}{idx}. [{section.title}](#{anchor})")
        return "\n".join(toc_lines) + "\n\n"

    def _generate_markdown(self, args: ReportGenerationArgs) -> str:
        """生成 Markdown 报告"""
        lines = []

        lines.append(f"# {args.title}\n")

        if args.include_timestamp:
            lines.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if args.author:
            lines.append(f"> 作者: {args.author}\n")

        lines.append("\n---\n")

        if args.include_toc and args.sections:
            lines.append(self._generate_toc(args.sections))

        if args.data_summary:
            lines.append("## 数据摘要\n")
            for key, value in args.data_summary.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("\n")

        for section in args.sections:
            heading = "#" * section.level
            lines.append(f"{heading} {section.title}\n")
            if section.content:
                lines.append(f"{section.content}\n")

        return "\n".join(lines)

    def _generate_html(self, args: ReportGenerationArgs) -> str:
        """生成 HTML 报告"""
        html_parts = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f"<title>{args.title}</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }",
            "h2 { color: #34495e; margin-top: 30px; }",
            "h3 { color: #7f8c8d; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }",
            "th { background-color: #3498db; color: white; }",
            "tr:nth-child(even) { background-color: #f2f2f2; }",
            "code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }",
            "pre { background-color: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }",
            "blockquote { border-left: 4px solid #3498db; margin: 0; padding-left: 20px; color: #7f8c8d; }",
            ".toc { background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }",
            ".toc ul { list-style-type: none; padding-left: 20px; }",
            ".toc a { color: #3498db; text-decoration: none; }",
            ".toc a:hover { text-decoration: underline; }",
            ".meta { color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{args.title}</h1>",
        ]

        if args.include_timestamp or args.author:
            html_parts.append('<div class="meta">')
            if args.include_timestamp:
                html_parts.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if args.author:
                html_parts.append(f" | 作者: {args.author}")
            html_parts.append("</div>")

        if args.include_toc and args.sections:
            html_parts.append('<div class="toc"><h3>目录</h3><ul>')
            for idx, section in enumerate(args.sections, 1):
                anchor = section.title.lower().replace(" ", "-")
                html_parts.append(f'<li><a href="#{anchor}">{idx}. {section.title}</a></li>')
            html_parts.append("</ul></div>")

        if args.data_summary:
            html_parts.append("<h2>数据摘要</h2><ul>")
            for key, value in args.data_summary.items():
                html_parts.append(f"<li><strong>{key}</strong>: {value}</li>")
            html_parts.append("</ul>")

        for section in args.sections:
            anchor = section.title.lower().replace(" ", "-")
            html_parts.append(f'<h{section.level} id="{anchor}">{section.title}</h{section.level}>')
            if section.content:
                html_parts.append(self._markdown_to_html(section.content))

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def _markdown_to_html(self, markdown_text: str) -> str:
        """简单 Markdown 转 HTML"""
        html = markdown_text

        html = html.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
        while "**" in html:
            html = html.replace("**", "<strong>", 1).replace("**", "</strong>", 1)

        html = html.replace("*", "<em>", 1).replace("*", "</em>", 1)
        while "*" in html:
            html = html.replace("*", "<em>", 1).replace("*", "</em>", 1)

        html = html.replace("`", "<code>", 1).replace("`", "</code>", 1)
        while "`" in html:
            html = html.replace("`", "<code>", 1).replace("`", "</code>", 1)

        lines = html.split("\n")
        html_lines = []
        for line in lines:
            if line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            else:
                html_lines.append(f"<p>{line}</p>" if line.strip() else "")

        return "\n".join(html_lines)

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = ReportGenerationArgs(**kwargs)

        try:
            if args.format == "markdown":
                content = self._generate_markdown(args)
            elif args.format == "html":
                content = self._generate_html(args)
            else:
                raise ToolError(f"不支持的格式: {args.format}")

            result = {
                "title": args.title,
                "format": args.format,
                "content_length": len(content),
            }

            if args.output_path:
                path = Path(args.output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                result["output_path"] = str(path)
                result["message"] = f"报告已保存到: {args.output_path}"
            else:
                result["content"] = content
                result["message"] = "报告生成成功"

            return result

        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"报告生成失败: {e}") from e


class DataReportTool(BaseTool):
    """数据报告工具

    自动分析数据并生成报告。
    """

    @property
    def name(self) -> str:
        return "data_report"

    @property
    def description(self) -> str:
        return "自动分析数据并生成数据分析报告"

    @property
    def capability(self) -> str:
        return "自动生成数据分析报告，包含数据概览、描述性统计、缺失值分析、分布分析"

    @property
    def limitations(self) -> list[str]:
        return [
            "仅支持基础统计分析",
            "不包含高级统计检验",
            "图表需要单独生成"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "快速生成数据概览报告",
            "数据质量初步评估",
            "探索性数据分析文档化"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return DataReportArgs

    def _generate_statistics_section(self, df: pd.DataFrame) -> ReportSection:
        """生成统计信息章节"""
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        content_lines = ["### 描述性统计\n"]

        if numeric_cols:
            desc = df[numeric_cols].describe()
            content_lines.append("| 统计量 | " + " | ".join(numeric_cols[:5]) + " |")
            content_lines.append("|" + "|".join(["---"] * (len(numeric_cols[:5]) + 1)) + "|")

            for stat in ["mean", "std", "min", "25%", "50%", "75%", "max"]:
                row = [stat]
                for col in numeric_cols[:5]:
                    val = desc.loc[stat, col]
                    row.append(f"{val:.2f}" if pd.notna(val) else "N/A")
                content_lines.append("| " + " | ".join(row) + " |")
        else:
            content_lines.append("无数值型列可供统计分析。")

        return ReportSection(
            title="统计信息",
            content="\n".join(content_lines),
            level=2,
        )

    def _generate_missing_section(self, df: pd.DataFrame) -> ReportSection:
        """生成缺失值分析章节"""
        content_lines = ["### 缺失值分析\n"]

        missing = df.isna().sum()
        total = len(df)

        content_lines.append("| 列名 | 缺失数量 | 缺失比例 |")
        content_lines.append("|---|---|---|")

        for col in df.columns:
            miss_count = missing[col]
            miss_ratio = miss_count / total * 100 if total > 0 else 0
            content_lines.append(f"| {col} | {miss_count} | {miss_ratio:.2f}% |")

        total_missing = missing.sum()
        total_cells = df.shape[0] * df.shape[1]
        content_lines.append(
            f"\n**总缺失率**: {total_missing}/{total_cells} ({total_missing/total_cells*100:.2f}%)"
        )

        return ReportSection(
            title="缺失值分析",
            content="\n".join(content_lines),
            level=2,
        )

    def _generate_distribution_section(self, df: pd.DataFrame) -> ReportSection:
        """生成分布分析章节"""
        content_lines = ["### 数据分布\n"]

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        if numeric_cols:
            content_lines.append("**数值型列分布:**\n")
            for col in numeric_cols[:5]:
                skew = df[col].skew()
                kurt = df[col].kurtosis()
                content_lines.append(f"- `{col}`: 偏度={skew:.2f}, 峰度={kurt:.2f}")

        if cat_cols:
            content_lines.append("\n**分类列分布:**\n")
            for col in cat_cols[:5]:
                unique_count = df[col].nunique()
                top_value = df[col].mode().iloc[0] if len(df[col].mode()) > 0 else "N/A"
                content_lines.append(f"- `{col}`: {unique_count} 个唯一值, 最常见值: {top_value}")

        return ReportSection(
            title="数据分布",
            content="\n".join(content_lines),
            level=2,
        )

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = DataReportArgs(**kwargs)

        try:
            df = pd.DataFrame(args.data)

            sections = [
                ReportSection(
                    title="数据概览",
                    content=f"- 数据维度: {df.shape[0]} 行 × {df.shape[1]} 列\n- 列名: {', '.join(df.columns.tolist())}",
                    level=2,
                )
            ]

            if args.include_statistics:
                sections.append(self._generate_statistics_section(df))

            if args.include_missing_analysis:
                sections.append(self._generate_missing_section(df))

            if args.include_distribution:
                sections.append(self._generate_distribution_section(df))

            report_args = ReportGenerationArgs(
                title=args.title,
                sections=sections,
                format=args.format,
                output_path=args.output_path,
                include_toc=True,
                include_timestamp=True,
                data_summary={
                    "行数": df.shape[0],
                    "列数": df.shape[1],
                    "数值型列": len(df.select_dtypes(include=["number"]).columns),
                    "分类列": len(df.select_dtypes(include=["object", "category"]).columns),
                },
            )

            report_tool = ReportGenerationTool()
            return report_tool.run(**report_args.model_dump())

        except Exception as e:
            raise ToolError(f"数据报告生成失败: {e}") from e
