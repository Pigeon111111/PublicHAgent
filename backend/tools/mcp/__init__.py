"""MCP 工具集成模块

提供 MCP (Model Context Protocol) 工具的集成支持。
"""

from backend.tools.mcp.adapter import MCPToolAdapter, adapt_mcp_tool
from backend.tools.mcp.client import MCPClient, MCPClientError, MCPServerConfig
from backend.tools.mcp.runtime import (
    MCPToolRuntime,
    close_mcp_tool_runtime,
    get_mcp_tool_runtime,
)
from backend.tools.mcp.wrapper import MCPWrappedTool

__all__ = [
    "MCPClient",
    "MCPClientError",
    "MCPServerConfig",
    "MCPToolRuntime",
    "MCPToolAdapter",
    "MCPWrappedTool",
    "adapt_mcp_tool",
    "get_mcp_tool_runtime",
    "close_mcp_tool_runtime",
]
