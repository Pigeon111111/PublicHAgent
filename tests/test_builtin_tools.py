"""内置工具单元测试"""

import json
from pathlib import Path

import pandas as pd
import pytest

from backend.tools.base import ToolError
from backend.tools.builtin.data_analysis import (
    DataCleaningTool,
    DataTransformationTool,
    StatisticalAnalysisTool,
)
from backend.tools.builtin.file_ops import (
    ListDirectoryTool,
    ReadDataFileTool,
    WriteDataFileTool,
)
from backend.tools.builtin.report import DataReportTool, ReportGenerationTool
from backend.tools.builtin.visualization import ChartGenerationTool, PlottingTool


class TestReadDataFileTool:
    """测试 ReadDataFileTool"""

    def test_read_csv_file(self, tmp_path: Path) -> None:
        """测试读取 CSV 文件"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age,city\nAlice,25,Beijing\nBob,30,Shanghai\n")

        tool = ReadDataFileTool()
        result = tool.run(file_path=str(csv_file))

        assert result["file_type"] == "csv"
        assert result["shape"]["rows"] == 2
        assert result["shape"]["columns"] == 3
        assert "name" in result["columns"]
        assert len(result["preview"]) == 2

    def test_read_json_file(self, tmp_path: Path) -> None:
        """测试读取 JSON 文件"""
        json_file = tmp_path / "test.json"
        data = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]
        json_file.write_text(json.dumps(data))

        tool = ReadDataFileTool()
        result = tool.run(file_path=str(json_file))

        assert result["file_type"] == "json"
        assert result["shape"]["rows"] == 2

    def test_read_nonexistent_file(self) -> None:
        """测试读取不存在的文件"""
        tool = ReadDataFileTool()
        with pytest.raises(ToolError, match="文件不存在"):
            tool.run(file_path="/nonexistent/file.csv")


class TestWriteDataFileTool:
    """测试 WriteDataFileTool"""

    def test_write_csv_file(self, tmp_path: Path) -> None:
        """测试写入 CSV 文件"""
        csv_file = tmp_path / "output.csv"
        data = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]

        tool = WriteDataFileTool()
        result = tool.run(file_path=str(csv_file), data=data)

        assert "成功写入数据文件" in result
        assert csv_file.exists()

        df = pd.read_csv(csv_file)
        assert len(df) == 2

    def test_write_json_file(self, tmp_path: Path) -> None:
        """测试写入 JSON 文件"""
        json_file = tmp_path / "output.json"
        data = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]

        tool = WriteDataFileTool()
        result = tool.run(file_path=str(json_file), data=data, file_type="json")

        assert "成功写入数据文件" in result
        assert json_file.exists()


class TestListDirectoryTool:
    """测试 ListDirectoryTool"""

    def test_list_directory(self, tmp_path: Path) -> None:
        """测试列出目录"""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.csv").write_text("content2")
        (tmp_path / "subdir").mkdir()

        tool = ListDirectoryTool()
        result = tool.run(directory=str(tmp_path))

        assert result["total_files"] == 2
        assert result["total_directories"] == 1

    def test_list_directory_with_pattern(self, tmp_path: Path) -> None:
        """测试带模式的目录列表"""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.csv").write_text("content2")

        tool = ListDirectoryTool()
        result = tool.run(directory=str(tmp_path), pattern="*.txt")

        assert result["total_files"] == 1
        assert result["files"][0]["name"] == "file1.txt"

    def test_list_nonexistent_directory(self) -> None:
        """测试列出不存在的目录"""
        tool = ListDirectoryTool()
        with pytest.raises(ToolError, match="目录不存在"):
            tool.run(directory="/nonexistent/directory")


class TestDataCleaningTool:
    """测试 DataCleaningTool"""

    def test_drop_missing(self) -> None:
        """测试删除缺失值"""
        data = [
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": None},
            {"name": "Charlie", "age": 30},
        ]

        tool = DataCleaningTool()
        result = tool.run(data=data, operations=["drop_missing"])

        assert result["rows_removed"] == 1
        assert len(result["cleaned_data"]) == 2

    def test_fill_missing_mean(self) -> None:
        """测试均值填充缺失值"""
        data = [
            {"name": "Alice", "age": 20},
            {"name": "Bob", "age": None},
            {"name": "Charlie", "age": 30},
        ]

        tool = DataCleaningTool()
        result = tool.run(data=data, operations=["fill_missing"], fill_method="mean")

        assert result["rows_removed"] == 0
        ages = [d["age"] for d in result["cleaned_data"]]
        assert 25.0 in ages

    def test_drop_duplicates(self) -> None:
        """测试删除重复值"""
        data = [
            {"name": "Alice", "age": 25},
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30},
        ]

        tool = DataCleaningTool()
        result = tool.run(data=data, operations=["drop_duplicates"])

        assert result["rows_removed"] == 1
        assert len(result["cleaned_data"]) == 2


class TestStatisticalAnalysisTool:
    """测试 StatisticalAnalysisTool"""

    def test_descriptive_stats(self) -> None:
        """测试描述性统计"""
        data = [
            {"name": "Alice", "age": 25, "score": 85},
            {"name": "Bob", "age": 30, "score": 90},
            {"name": "Charlie", "age": 35, "score": 75},
        ]

        tool = StatisticalAnalysisTool()
        result = tool.run(data=data, analysis_type="descriptive")

        assert "statistics" in result
        assert "age" in result["statistics"]
        assert "score" in result["statistics"]

    def test_correlation_analysis(self) -> None:
        """测试相关性分析"""
        data = [
            {"x": 1, "y": 2},
            {"x": 2, "y": 4},
            {"x": 3, "y": 6},
            {"x": 4, "y": 8},
        ]

        tool = StatisticalAnalysisTool()
        result = tool.run(data=data, analysis_type="correlation")

        assert "correlation_matrix" in result
        corr = result["correlation_matrix"]["x"]["y"]
        assert abs(corr - 1.0) < 0.01

    def test_normality_test(self) -> None:
        """测试正态性检验"""
        import numpy as np

        np.random.seed(42)
        data = [{"value": x} for x in np.random.normal(0, 1, 100)]

        tool = StatisticalAnalysisTool()
        result = tool.run(data=data, analysis_type="normality")

        assert "normality_tests" in result
        assert "value" in result["normality_tests"]


class TestDataTransformationTool:
    """测试 DataTransformationTool"""

    def test_normalize(self) -> None:
        """测试归一化"""
        data = [{"value": 10}, {"value": 20}, {"value": 30}]

        tool = DataTransformationTool()
        result = tool.run(data=data, transformation="normalize", columns=["value"])

        values = [d["value"] for d in result["transformed_data"]]
        assert min(values) == 0.0
        assert max(values) == 1.0

    def test_standardize(self) -> None:
        """测试标准化"""
        data = [{"value": 10}, {"value": 20}, {"value": 30}]

        tool = DataTransformationTool()
        result = tool.run(data=data, transformation="standardize", columns=["value"])

        values = [d["value"] for d in result["transformed_data"]]
        assert abs(sum(values)) < 0.01

    def test_label_encode(self) -> None:
        """测试标签编码"""
        data = [{"category": "A"}, {"category": "B"}, {"category": "A"}]

        tool = DataTransformationTool()
        result = tool.run(data=data, transformation="label_encode", columns=["category"])

        categories = [d["category"] for d in result["transformed_data"]]
        assert set(categories) == {0, 1}


class TestPlottingTool:
    """测试 PlottingTool"""

    def test_plot_line(self) -> None:
        """测试折线图"""
        data = [{"x": 1, "y": 10}, {"x": 2, "y": 20}, {"x": 3, "y": 15}]

        tool = PlottingTool()
        result = tool.run(
            data=data,
            chart_type="line",
            x_column="x",
            y_column="y",
            output_format="base64",
        )

        assert result.startswith("data:image/png;base64,")

    def test_plot_bar(self) -> None:
        """测试柱状图"""
        data = [{"category": "A", "value": 10}, {"category": "B", "value": 20}]

        tool = PlottingTool()
        result = tool.run(
            data=data,
            chart_type="bar",
            x_column="category",
            y_column="value",
            output_format="base64",
        )

        assert result.startswith("data:image/png;base64,")

    def test_plot_to_file(self, tmp_path: Path) -> None:
        """测试保存图表到文件"""
        data = [{"x": 1, "y": 10}, {"x": 2, "y": 20}]
        output_file = tmp_path / "chart.png"

        tool = PlottingTool()
        result = tool.run(
            data=data,
            chart_type="line",
            x_column="x",
            y_column="y",
            output_format="file",
            output_path=str(output_file),
        )

        assert output_file.exists()
        assert "已保存到" in result


class TestChartGenerationTool:
    """测试 ChartGenerationTool"""

    def test_correlation_matrix(self) -> None:
        """测试相关性矩阵图"""
        data = [
            {"a": 1, "b": 2, "c": 3},
            {"a": 2, "b": 4, "c": 6},
            {"a": 3, "b": 6, "c": 9},
        ]

        tool = ChartGenerationTool()
        result = tool.run(
            data=data,
            chart_type="correlation_matrix",
            output_format="base64",
        )

        assert result.startswith("data:image/png;base64,")

    def test_distribution(self) -> None:
        """测试分布图"""
        import numpy as np

        np.random.seed(42)
        data = [{"value": x} for x in np.random.normal(0, 1, 50)]

        tool = ChartGenerationTool()
        result = tool.run(
            data=data,
            chart_type="distribution",
            columns=["value"],
            output_format="base64",
        )

        assert result.startswith("data:image/png;base64,")


class TestReportGenerationTool:
    """测试 ReportGenerationTool"""

    def test_generate_markdown_report(self) -> None:
        """测试生成 Markdown 报告"""
        tool = ReportGenerationTool()
        result = tool.run(
            title="测试报告",
            format="markdown",
            sections=[
                {"title": "概述", "content": "这是一个测试报告", "level": 2},
                {"title": "数据", "content": "- 项目1\n- 项目2", "level": 2},
            ],
        )

        assert result["format"] == "markdown"
        assert result["content_length"] > 0
        assert "测试报告" in result["content"]

    def test_generate_html_report(self) -> None:
        """测试生成 HTML 报告"""
        tool = ReportGenerationTool()
        result = tool.run(
            title="测试报告",
            format="html",
            sections=[{"title": "概述", "content": "这是一个测试报告", "level": 2}],
        )

        assert result["format"] == "html"
        assert "<!DOCTYPE html>" in result["content"]
        assert "测试报告" in result["content"]

    def test_save_report_to_file(self, tmp_path: Path) -> None:
        """测试保存报告到文件"""
        report_file = tmp_path / "report.md"

        tool = ReportGenerationTool()
        result = tool.run(
            title="测试报告",
            format="markdown",
            output_path=str(report_file),
            sections=[{"title": "概述", "content": "测试内容", "level": 2}],
        )

        assert report_file.exists()
        assert result["output_path"] == str(report_file)


class TestDataReportTool:
    """测试 DataReportTool"""

    def test_generate_data_report(self) -> None:
        """测试生成数据报告"""
        data = [
            {"name": "Alice", "age": 25, "score": 85.5},
            {"name": "Bob", "age": 30, "score": 90.0},
            {"name": "Charlie", "age": None, "score": 75.5},
        ]

        tool = DataReportTool()
        result = tool.run(
            data=data,
            title="数据分析报告",
            format="markdown",
        )

        assert result["format"] == "markdown"
        assert "数据分析报告" in result["content"]
        assert "统计信息" in result["content"]
        assert "缺失值分析" in result["content"]

    def test_generate_html_data_report(self) -> None:
        """测试生成 HTML 数据报告"""
        data = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]

        tool = DataReportTool()
        result = tool.run(
            data=data,
            title="数据分析报告",
            format="html",
        )

        assert result["format"] == "html"
        assert "<!DOCTYPE html>" in result["content"]


class TestBuiltinToolsIntegration:
    """测试内置工具集成"""

    def test_full_analysis_workflow(self, tmp_path: Path) -> None:
        """测试完整分析工作流"""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age,score\nAlice,25,85\nBob,30,90\nCharlie,35,75\n")

        read_tool = ReadDataFileTool()
        data_result = read_tool.run(file_path=str(csv_file))
        assert data_result["shape"]["rows"] == 3

        cleaning_tool = DataCleaningTool()
        cleaned_result = cleaning_tool.run(
            data=data_result["preview"],
            operations=["drop_duplicates"],
        )
        assert len(cleaned_result["cleaned_data"]) == 3

        stats_tool = StatisticalAnalysisTool()
        stats_result = stats_tool.run(
            data=cleaned_result["cleaned_data"],
            analysis_type="descriptive",
        )
        assert "statistics" in stats_result

    def test_all_tools_registered(self) -> None:
        """测试所有工具可被导入"""
        from backend.tools.builtin import get_all_builtin_tools

        tools = get_all_builtin_tools()
        assert len(tools) == 13

        tool_names = [t.name for t in tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "data_cleaning" in tool_names
        assert "statistical_analysis" in tool_names
        assert "plotting" in tool_names
        assert "report_generation" in tool_names
