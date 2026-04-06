"""MCP 工具集成模块

提供 MCP (Model Context Protocol) 工具的集成支持。
"""

from backend.tools.mcp.adapter import MCPToolAdapter, adapt_mcp_tool
from backend.tools.mcp.client import MCPClient, MCPClientError, MCPServerConfig

__all__ = [
    "MCPClient",
    "MCPClientError",
    "MCPServerConfig",
    "MCPToolAdapter",
    "adapt_mcp_tool",
]
