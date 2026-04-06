"""内置工具模块

提供文件操作、数据分析、可视化、报告生成等内置工具。
"""

from backend.tools.builtin.data_analysis import (
    DataCleaningTool,
    DataTransformationTool,
    StatisticalAnalysisTool,
)
from backend.tools.builtin.file_ops import (
    EditFileTool,
    ListDirectoryTool,
    ReadDataFileTool,
    ReadFileTool,
    WriteDataFileTool,
    WriteFileTool,
)
from backend.tools.builtin.report import DataReportTool, ReportGenerationTool
from backend.tools.builtin.visualization import ChartGenerationTool, PlottingTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ReadDataFileTool",
    "WriteDataFileTool",
    "ListDirectoryTool",
    "DataCleaningTool",
    "StatisticalAnalysisTool",
    "DataTransformationTool",
    "PlottingTool",
    "ChartGenerationTool",
    "ReportGenerationTool",
    "DataReportTool",
]


def get_all_builtin_tools() -> list:
    """获取所有内置工具实例"""
    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        ReadDataFileTool(),
        WriteDataFileTool(),
        ListDirectoryTool(),
        DataCleaningTool(),
        StatisticalAnalysisTool(),
        DataTransformationTool(),
        PlottingTool(),
        ChartGenerationTool(),
        ReportGenerationTool(),
        DataReportTool(),
    ]
