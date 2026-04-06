"""工具系统单元测试"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.tools.base import BaseTool, ToolError
from backend.tools.builtin.file_ops import EditFileTool, ReadFileTool, WriteFileTool
from backend.tools.registry import (
    ToolRegistry,
    get_tool_registry,
    reset_tool_registry,
)


class MockTool(BaseTool):
    """模拟工具用于测试"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "模拟工具"

    @property
    def args_schema(self) -> type[BaseModel]:
        return MockToolArgs

    def run(self, **kwargs: "MockToolArgs") -> str:
        return f"Mock tool executed with {kwargs}"


class MockToolArgs(BaseModel):
    """模拟工具参数"""

    value: str


class TestBaseTool:
    """测试 BaseTool"""

    def test_get_openai_tool_definition(self) -> None:
        """测试获取 OpenAI 工具定义"""
        tool = MockTool()
        definition = tool.get_openai_tool_definition()

        assert definition["type"] == "function"
        assert definition["function"]["name"] == "mock_tool"
        assert definition["function"]["description"] == "模拟工具"
        assert "parameters" in definition["function"]

    def test_validate_args_success(self) -> None:
        """测试参数验证成功"""
        tool = MockTool()
        validated = tool.validate_args(value="test")
        assert validated.value == "test"

    def test_validate_args_failure(self) -> None:
        """测试参数验证失败"""
        tool = MockTool()
        with pytest.raises(ToolError, match="参数验证失败"):
            tool.validate_args(invalid_param="test")


class TestToolRegistry:
    """测试 ToolRegistry"""

    def setup_method(self) -> None:
        """每个测试前重置全局注册表"""
        reset_tool_registry()

    def teardown_method(self) -> None:
        """每个测试后重置全局注册表"""
        reset_tool_registry()

    def test_register_tool(self) -> None:
        """测试注册工具"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        assert registry.has("mock_tool")

    def test_register_duplicate_tool(self) -> None:
        """测试注册重复工具"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        with pytest.raises(ToolError, match="工具已存在"):
            registry.register(tool)

    def test_unregister_tool(self) -> None:
        """测试注销工具"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        registry.unregister("mock_tool")
        assert not registry.has("mock_tool")

    def test_unregister_nonexistent_tool(self) -> None:
        """测试注销不存在的工具"""
        registry = ToolRegistry()
        with pytest.raises(ToolError, match="工具不存在"):
            registry.unregister("nonexistent")

    def test_get_tool(self) -> None:
        """测试获取工具"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        retrieved = registry.get("mock_tool")
        assert retrieved.name == "mock_tool"

    def test_get_nonexistent_tool(self) -> None:
        """测试获取不存在的工具"""
        registry = ToolRegistry()
        with pytest.raises(ToolError, match="工具不存在"):
            registry.get("nonexistent")

    def test_list_tools(self) -> None:
        """测试列出所有工具"""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = ReadFileTool()
        registry.register(tool1)
        registry.register(tool2)
        tools = registry.list_tools()
        assert "mock_tool" in tools
        assert "read_file" in tools

    def test_get_all_tools(self) -> None:
        """测试获取所有工具"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        tools = registry.get_all_tools()
        assert len(tools) == 1

    def test_get_openai_tools_definition(self) -> None:
        """测试获取 OpenAI 工具定义"""
        registry = ToolRegistry()
        tool = ReadFileTool()
        registry.register(tool)
        definitions = registry.get_openai_tools_definition()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "read_file"

    def test_execute_tool(self) -> None:
        """测试执行工具"""
        registry = ToolRegistry()
        read_tool = ReadFileTool()
        registry.register(read_tool)
        test_file = Path("test.txt")
        test_file.write_text("test content")

        result = registry.execute("read_file", file_path=str(test_file))
        assert result == "test content"

        test_file.unlink()

    def test_execute_with_validation(self) -> None:
        """测试执行带参数验证的工具"""
        registry = ToolRegistry()
        read_tool = ReadFileTool()
        registry.register(read_tool)
        test_file = Path("test.txt")
        test_file.write_text("test content")

        result = registry.execute(
            "read_file", file_path=str(test_file), encoding="utf-8"
        )
        assert result == "test content"

        test_file.unlink()

    def test_clear(self) -> None:
        """测试清空注册表"""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        registry.clear()
        assert len(registry.list_tools()) == 0


class TestGetToolRegistry:
    """测试全局工具注册表"""

    def setup_method(self) -> None:
        """每个测试前重置全局注册表"""
        reset_tool_registry()

    def teardown_method(self) -> None:
        """每个测试后重置全局注册表"""
        reset_tool_registry()

    def test_get_tool_registry(self) -> None:
        """测试获取全局工具注册表"""
        registry1 = get_tool_registry()
        registry2 = get_tool_registry()
        assert registry1 is registry2


class TestReadFileTool:
    """测试 ReadFileTool"""

    def test_read_file_success(self, tmp_path: Path) -> None:
        """测试读取文件成功"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content", encoding="utf-8")

        tool = ReadFileTool()
        result = tool.run(file_path=str(test_file), encoding="utf-8")
        assert result == "test content"

    def test_read_file_not_found(self) -> None:
        """测试读取不存在的文件"""
        tool = ReadFileTool()
        with pytest.raises(ToolError, match="文件不存在"):
            tool.run(file_path="/nonexistent/file.txt")

    def test_read_file_not_a_file(self, tmp_path: Path) -> None:
        """测试读取目录而非文件"""
        tool = ReadFileTool()
        with pytest.raises(ToolError, match="不是文件"):
            tool.run(file_path=str(tmp_path))

    def test_read_file_with_custom_encoding(self, tmp_path: Path) -> None:
        """测试自定义编码读取"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")

        tool = ReadFileTool()
        result = tool.run(file_path=str(test_file), encoding="utf-8")
        assert result == "测试内容"


class TestWriteFileTool:
    """测试 WriteFileTool"""

    def test_write_file_success(self, tmp_path: Path) -> None:
        """测试写入文件成功"""
        test_file = tmp_path / "test.txt"
        tool = WriteFileTool()
        result = tool.run(file_path=str(test_file), content="test content")

        assert "成功写入文件" in result
        assert test_file.read_text() == "test content"

    def test_write_file_create_parent_dirs(self, tmp_path: Path) -> None:
        """测试创建父目录"""
        test_file = tmp_path / "subdir" / "test.txt"
        tool = WriteFileTool()
        result = tool.run(file_path=str(test_file), content="test content")

        assert "成功写入文件" in result
        assert test_file.exists()

    def test_write_file_append_mode(self, tmp_path: Path) -> None:
        """测试追加写入模式"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line1\n")

        tool = WriteFileTool()
        tool.run(file_path=str(test_file), content="line2", mode="a")

        assert test_file.read_text() == "line1\nline2"


class TestEditFileTool:
    """测试 EditFileTool"""

    def test_edit_file_success(self, tmp_path: Path) -> None:
        """测试编辑文件成功"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        tool = EditFileTool()
        result = tool.run(
            file_path=str(test_file), old_str="world", new_str="python"
        )

        assert "成功编辑文件" in result
        assert test_file.read_text() == "hello python"

    def test_edit_file_not_found(self) -> None:
        """测试编辑不存在的文件"""
        tool = EditFileTool()
        with pytest.raises(ToolError, match="文件不存在"):
            tool.run(
                file_path="/nonexistent/file.txt", old_str="old", new_str="new"
            )

    def test_edit_file_not_found_string(self, tmp_path: Path) -> None:
        """测试编辑文件时未找到要替换的内容"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        tool = EditFileTool()
        with pytest.raises(ToolError, match="未找到要替换的内容"):
            tool.run(
                file_path=str(test_file), old_str="not found", new_str="new"
            )


class TestToolIntegration:
    """测试工具集成"""

    def test_registry_with_file_tools(self, tmp_path: Path) -> None:
        """测试注册表与文件工具集成"""
        registry = ToolRegistry()

        read_tool = ReadFileTool()
        write_tool = WriteFileTool()

        registry.register(read_tool)
        registry.register(write_tool)

        assert registry.has("read_file")
        assert registry.has("write_file")

        test_file = tmp_path / "test.txt"
        registry.execute("write_file", file_path=str(test_file), content="test")

        content = registry.execute("read_file", file_path=str(test_file))
        assert content == "test"

    def test_openai_format_export(self) -> None:
        """测试导出 OpenAI 格式"""
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())

        definitions = registry.get_openai_tools_definition()
        assert len(definitions) == 2

        func_names = [d["function"]["name"] for d in definitions]
        assert "read_file" in func_names
        assert "write_file" in func_names
