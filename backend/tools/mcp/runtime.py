"""MCP 工具运行时。

负责维持 MCP 连接，并把工具加载到项目运行时。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from backend.tools.base import BaseTool
from backend.tools.mcp.client import MCPClient
from backend.tools.mcp.wrapper import MCPWrappedTool


class MCPToolRuntime:
    """管理 MCP 连接和已加载工具。"""

    def __init__(self, config_path: str | Path = "backend/config/mcp.json") -> None:
        self._config_path = Path(config_path)
        self._client: MCPClient | None = None
        self._tools: list[BaseTool] = []
        self._last_error: str | None = None
        self._lock = asyncio.Lock()

    async def load_tools(self, force: bool = False) -> list[BaseTool]:
        """加载 MCP 工具并缓存。"""
        if self._tools and not force:
            return list(self._tools)

        async with self._lock:
            if self._tools and not force:
                return list(self._tools)

            if force:
                await self.close()

            client = self._client or MCPClient(config_path=self._config_path)
            try:
                await client.connect()
                tools: list[BaseTool] = []
                for server_name in client.list_servers():
                    server_tools = await client.get_tools_by_server(server_name)
                    tools.extend(
                        MCPWrappedTool(server_name=server_name, tool=tool)
                        for tool in server_tools
                    )
                self._client = client
                self._tools = tools
                self._last_error = None
                return list(self._tools)
            except Exception as exc:
                self._last_error = str(exc)
                await self.close()
                raise

    async def close(self) -> None:
        """关闭 MCP 客户端并清理缓存。"""
        if self._client is not None:
            await self._client.disconnect()
        self._client = None
        self._tools = []

    def snapshot(self) -> dict[str, Any]:
        """返回 MCP 运行时状态。"""
        return {
            "connected": self._client is not None and self._client.is_connected,
            "tool_count": len(self._tools),
            "tool_names": [tool.name for tool in self._tools],
            "last_error": self._last_error,
            "config_path": str(self._config_path),
        }


_mcp_runtime: MCPToolRuntime | None = None


def get_mcp_tool_runtime() -> MCPToolRuntime:
    """获取全局 MCP 运行时。"""
    global _mcp_runtime
    if _mcp_runtime is None:
        _mcp_runtime = MCPToolRuntime()
    return _mcp_runtime


async def close_mcp_tool_runtime() -> None:
    """关闭全局 MCP 运行时。"""
    global _mcp_runtime
    if _mcp_runtime is not None:
        await _mcp_runtime.close()
        _mcp_runtime = None
