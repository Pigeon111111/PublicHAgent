"""文件操作工具

提供文件读取、写入、编辑等操作工具。
支持 CSV、XLSX、JSON 等多种数据格式。
"""

from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from backend.tools.base import BaseTool, ToolError


class ReadFileArgs(BaseModel):
    """读取文件参数"""

    file_path: str = Field(..., description="要读取的文件路径")
    encoding: str = Field(default="utf-8", description="文件编码")


class WriteFileArgs(BaseModel):
    """写入文件参数"""

    file_path: str = Field(..., description="要写入的文件路径")
    content: str = Field(..., description="要写入的内容")
    encoding: str = Field(default="utf-8", description="文件编码")
    mode: str = Field(default="w", description="写入模式，'w' 为覆盖，'a' 为追加")


class EditFileArgs(BaseModel):
    """编辑文件参数"""

    file_path: str = Field(..., description="要编辑的文件路径")
    old_str: str = Field(..., description="要搜索的字符串")
    new_str: str = Field(..., description="要替换的字符串")
    encoding: str = Field(default="utf-8", description="文件编码")


class ReadDataFileArgs(BaseModel):
    """读取数据文件参数"""

    file_path: str = Field(..., description="要读取的数据文件路径")
    file_type: str = Field(default="auto", description="文件类型: auto/csv/xlsx/json")
    sheet_name: str | int | None = Field(default=0, description="Excel 工作表名称或索引")
    encoding: str = Field(default="utf-8", description="文件编码")
    delimiter: str = Field(default=",", description="CSV 分隔符")


class WriteDataFileArgs(BaseModel):
    """写入数据文件参数"""

    file_path: str = Field(..., description="要写入的数据文件路径")
    data: list[dict[str, Any]] = Field(..., description="要写入的数据（字典列表）")
    file_type: str = Field(default="auto", description="文件类型: auto/csv/xlsx/json")
    sheet_name: str = Field(default="Sheet1", description="Excel 工作表名称")
    encoding: str = Field(default="utf-8", description="文件编码")
    index: bool = Field(default=False, description="是否写入索引列")


class ReadFileTool(BaseTool):
    """读取文件工具"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取指定文件的内容"

    @property
    def capability(self) -> str:
        return "读取文本文件内容，支持指定编码格式"

    @property
    def limitations(self) -> list[str]:
        return [
            "只能读取文本文件，不支持二进制文件",
            "文件大小受内存限制",
            "不支持远程文件路径"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "读取配置文件、日志文件等文本内容",
            "查看小型文本文件",
            "读取代码文件"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return ReadFileArgs

    def run(self, **kwargs: Any) -> str:
        args = ReadFileArgs(**kwargs)
        path = Path(args.file_path)

        if not path.exists():
            raise ToolError(f"文件不存在: {args.file_path}")

        if not path.is_file():
            raise ToolError(f"不是文件: {args.file_path}")

        try:
            return path.read_text(encoding=args.encoding)
        except Exception as e:
            raise ToolError(f"读取文件失败: {e}") from e


class WriteFileTool(BaseTool):
    """写入文件工具"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "将内容写入指定文件"

    @property
    def capability(self) -> str:
        return "写入文本内容到文件，支持覆盖和追加模式"

    @property
    def limitations(self) -> list[str]:
        return [
            "只能写入文本内容",
            "不自动备份原有文件",
            "需要文件系统写入权限"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "保存分析结果到文件",
            "创建配置文件",
            "写入日志文件"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return WriteFileArgs

    def run(self, **kwargs: Any) -> str:
        args = WriteFileArgs(**kwargs)
        path = Path(args.file_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, mode=args.mode, encoding=args.encoding) as f:
                f.write(args.content)
            return f"成功写入文件: {args.file_path}"
        except Exception as e:
            raise ToolError(f"写入文件失败: {e}") from e


class EditFileTool(BaseTool):
    """编辑文件工具"""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "编辑文件，搜索并替换指定内容"

    @property
    def capability(self) -> str:
        return "在文件中搜索并替换指定的文本内容"

    @property
    def limitations(self) -> list[str]:
        return [
            "只能替换第一个匹配项",
            "不支持正则表达式",
            "需要精确匹配要替换的内容"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "修改配置文件中的特定配置项",
            "更新代码文件中的特定代码",
            "批量修改文本文件内容"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return EditFileArgs

    def run(self, **kwargs: Any) -> str:
        args = EditFileArgs(**kwargs)
        path = Path(args.file_path)

        if not path.exists():
            raise ToolError(f"文件不存在: {args.file_path}")

        if not path.is_file():
            raise ToolError(f"不是文件: {args.file_path}")

        try:
            content = path.read_text(encoding=args.encoding)

            if args.old_str not in content:
                raise ToolError(f"未找到要替换的内容: {args.old_str[:50]}...")

            new_content = content.replace(args.old_str, args.new_str, 1)
            path.write_text(new_content, encoding=args.encoding)

            return f"成功编辑文件: {args.file_path}"
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"编辑文件失败: {e}") from e


class ReadDataFileTool(BaseTool):
    """读取数据文件工具

    支持 CSV、Excel、JSON 格式的数据文件读取。
    """

    @property
    def name(self) -> str:
        return "read_data_file"

    @property
    def description(self) -> str:
        return "读取数据文件（CSV、Excel、JSON），返回数据摘要和前几行数据"

    @property
    def capability(self) -> str:
        return "读取结构化数据文件（CSV、Excel、JSON），返回数据预览和基本信息"

    @property
    def limitations(self) -> list[str]:
        return [
            "大文件可能导致内存问题",
            "Excel 文件需要 openpyxl 库支持",
            "不支持加密的 Excel 文件",
            "不支持嵌套的 JSON 结构"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "读取数据分析所需的原始数据",
            "查看数据文件结构和内容预览",
            "导入公共卫生监测数据"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return ReadDataFileArgs

    def _detect_file_type(self, path: Path) -> str:
        """根据文件扩展名检测文件类型"""
        suffix = path.suffix.lower()
        type_map = {
            ".csv": "csv",
            ".xlsx": "xlsx",
            ".xls": "xlsx",
            ".json": "json",
        }
        return type_map.get(suffix, "csv")

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = ReadDataFileArgs(**kwargs)
        path = Path(args.file_path)

        if not path.exists():
            raise ToolError(f"文件不存在: {args.file_path}")

        if not path.is_file():
            raise ToolError(f"不是文件: {args.file_path}")

        file_type = args.file_type
        if file_type == "auto":
            file_type = self._detect_file_type(path)

        try:
            if file_type == "csv":
                df = pd.read_csv(path, encoding=args.encoding, delimiter=args.delimiter)
            elif file_type == "xlsx":
                df = pd.read_excel(path, sheet_name=args.sheet_name)
            elif file_type == "json":
                df = pd.read_json(path, encoding=args.encoding)
            else:
                raise ToolError(f"不支持的文件类型: {file_type}")

            result = {
                "file_path": str(path),
                "file_type": file_type,
                "shape": {"rows": len(df), "columns": len(df.columns)},
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "preview": df.head(10).to_dict(orient="records"),
                "missing_values": {col: int(df[col].isna().sum()) for col in df.columns},
            }
            return result
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"读取数据文件失败: {e}") from e


class WriteDataFileTool(BaseTool):
    """写入数据文件工具

    支持 CSV、Excel、JSON 格式的数据文件写入。
    """

    @property
    def name(self) -> str:
        return "write_data_file"

    @property
    def description(self) -> str:
        return "将数据写入文件（CSV、Excel、JSON）"

    @property
    def capability(self) -> str:
        return "将结构化数据写入文件，支持 CSV、Excel、JSON 格式"

    @property
    def limitations(self) -> list[str]:
        return [
            "数据必须是字典列表格式",
            "大文件写入可能较慢",
            "不支持追加模式"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "保存处理后的分析结果",
            "导出数据报告",
            "数据格式转换"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return WriteDataFileArgs

    def _detect_file_type(self, path: Path) -> str:
        """根据文件扩展名检测文件类型"""
        suffix = path.suffix.lower()
        type_map = {
            ".csv": "csv",
            ".xlsx": "xlsx",
            ".xls": "xlsx",
            ".json": "json",
        }
        return type_map.get(suffix, "csv")

    def run(self, **kwargs: Any) -> str:
        args = WriteDataFileArgs(**kwargs)
        path = Path(args.file_path)

        file_type = args.file_type
        if file_type == "auto":
            file_type = self._detect_file_type(path)

        try:
            df = pd.DataFrame(args.data)
            path.parent.mkdir(parents=True, exist_ok=True)

            if file_type == "csv":
                df.to_csv(path, index=args.index, encoding=args.encoding)
            elif file_type == "xlsx":
                df.to_excel(path, sheet_name=args.sheet_name, index=args.index)
            elif file_type == "json":
                df.to_json(path, orient="records", force_ascii=False, indent=2)
            else:
                raise ToolError(f"不支持的文件类型: {file_type}")

            return f"成功写入数据文件: {args.file_path}（{len(df)} 行，{len(df.columns)} 列）"
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"写入数据文件失败: {e}") from e


class ListDirectoryArgs(BaseModel):
    """列出目录参数"""

    directory: str = Field(..., description="要列出的目录路径")
    pattern: str = Field(default="*", description="文件匹配模式（glob 格式）")
    recursive: bool = Field(default=False, description="是否递归列出子目录")


class ListDirectoryTool(BaseTool):
    """列出目录工具"""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "列出目录中的文件和子目录"

    @property
    def capability(self) -> str:
        return "列出指定目录下的文件和子目录，支持通配符匹配和递归遍历"

    @property
    def limitations(self) -> list[str]:
        return [
            "需要目录读取权限",
            "大量文件时可能较慢",
            "不支持远程目录"
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "浏览数据文件目录结构",
            "查找特定类型的文件",
            "了解项目文件组织"
        ]

    @property
    def args_schema(self) -> type[BaseModel]:
        return ListDirectoryArgs

    def run(self, **kwargs: Any) -> dict[str, Any]:
        args = ListDirectoryArgs(**kwargs)
        path = Path(args.directory)

        if not path.exists():
            raise ToolError(f"目录不存在: {args.directory}")

        if not path.is_dir():
            raise ToolError(f"不是目录: {args.directory}")

        try:
            if args.recursive:
                items = list(path.rglob(args.pattern))
            else:
                items = list(path.glob(args.pattern))

            files: list[dict[str, Any]] = []
            directories: list[dict[str, Any]] = []

            for item in items:
                item_info: dict[str, Any] = {
                    "name": item.name,
                    "path": str(item),
                    "relative_path": str(item.relative_to(path)),
                }
                if item.is_file():
                    item_info["size"] = item.stat().st_size
                    item_info["extension"] = item.suffix
                    files.append(item_info)
                elif item.is_dir():
                    directories.append(item_info)

            return {
                "directory": str(path),
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories),
            }
        except Exception as e:
            raise ToolError(f"列出目录失败: {e}") from e
