"""MCP 工具适配器

将 MCP 工具转换为 LangChain StructuredTool。
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

try:
    from langchain_core.tools import StructuredTool
except ImportError:
    StructuredTool = None  # type: ignore[misc,assignment]


class MCPToolAdapter:
    """MCP 工具适配器

    将 MCP 工具适配为 LangChain StructuredTool 格式，
    支持工具发现和动态加载。
    """

    @staticmethod
    def adapt_tool(mcp_tool: Any) -> StructuredTool:
        """将 MCP 工具适配为 LangChain StructuredTool

        Args:
            mcp_tool: MCP 工具对象

        Returns:
            LangChain StructuredTool
        """
        if StructuredTool is None:
            raise ImportError("langchain 未安装，请运行: pip install langchain")

        tool_name = getattr(mcp_tool, "name", "unknown_mcp_tool")
        tool_description = getattr(mcp_tool, "description", "")
        tool_schema = getattr(mcp_tool, "args_schema", None)
        tool_func = getattr(mcp_tool, "func", None)

        if tool_schema is None:
            tool_schema = MCPToolArgs

        if tool_func is None:
            tool_func = MCPToolAdapter._create_wrapper(mcp_tool)

        return StructuredTool(
            name=tool_name,
            description=tool_description,
            args_schema=tool_schema,
            func=tool_func,
        )

    @staticmethod
    def _create_wrapper(mcp_tool: Any) -> Callable[..., Any]:
        """创建工具执行包装器

        Args:
            mcp_tool: MCP 工具对象

        Returns:
            执行函数
        """
        async def wrapper(**kwargs: Any) -> Any:
            func = getattr(mcp_tool, "func", None)
            ainvoke = getattr(mcp_tool, "ainvoke", None)

            if ainvoke:
                return await ainvoke(kwargs)
            elif func:
                return func(**kwargs)
            else:
                raise ValueError(f"工具 {mcp_tool.name} 没有可执行的函数")

        return wrapper

    @staticmethod
    def adapt_tools(mcp_tools: list[Any]) -> list[StructuredTool]:
        """批量适配 MCP 工具

        Args:
            mcp_tools: MCP 工具列表

        Returns:
            LangChain StructuredTool 列表
        """
        return [MCPToolAdapter.adapt_tool(tool) for tool in mcp_tools]


class MCPToolArgs(BaseModel):
    """MCP 工具通用参数"""

    pass


def adapt_mcp_tool(mcp_tool: Any) -> StructuredTool:
    """便捷函数：适配单个 MCP 工具

    Args:
        mcp_tool: MCP 工具对象

    Returns:
        LangChain StructuredTool
    """
    return MCPToolAdapter.adapt_tool(mcp_tool)


def adapt_mcp_tools(mcp_tools: list[Any]) -> list[StructuredTool]:
    """便捷函数：批量适配 MCP 工具

    Args:
        mcp_tools: MCP 工具列表

    Returns:
        LangChain StructuredTool 列表
    """
    return MCPToolAdapter.adapt_tools(mcp_tools)
