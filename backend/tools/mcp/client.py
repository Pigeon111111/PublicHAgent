"""MCP 客户端实现

使用 langchain-mcp-adapters 实现 MCP 服务器的连接和工具获取。
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    from langchain_mcp_adapters import MultiServerMCPClient  # type: ignore[attr-defined]
    from langchain_mcp_adapters.sessions import StdioServerParameters
except ImportError:
    MultiServerMCPClient = None  # type: ignore[misc,assignment]
    StdioServerParameters = None  # type: ignore[misc,assignment]


class MCPClientError(Exception):
    """MCP 客户端错误"""

    pass


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    name: str = Field(..., description="服务器名称")
    description: str = Field(default="", description="服务器描述")
    command: str | None = Field(default=None, description="启动命令（stdio 传输必需）")
    args: list[str] = Field(default_factory=list, description="命令参数")
    enabled: bool = Field(default=True, description="是否启用")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    transport: str = Field(default="stdio", description="传输方式: stdio 或 sse")

    # SSE 传输相关配置
    url: str | None = Field(default=None, description="SSE 服务器 URL")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPServerConfig":
        """从字典创建配置"""
        return cls(**data)


class MCPConfig(BaseModel):
    """MCP 总配置"""

    mcp_servers: list[MCPServerConfig] = Field(default_factory=list, description="服务器列表")
    connection_timeout: int = Field(default=30, description="连接超时（秒）")
    retry_attempts: int = Field(default=3, description="重试次数")

    @classmethod
    def from_file(cls, config_path: str | Path) -> "MCPConfig":
        """从配置文件加载"""
        path = Path(config_path)
        if not path.exists():
            raise MCPClientError(f"配置文件不存在: {config_path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        servers = []
        for server_data in data.get("mcp_servers", []):
            servers.append(MCPServerConfig.from_dict(server_data))

        return cls(
            mcp_servers=servers,
            connection_timeout=data.get("connection_timeout", 30),
            retry_attempts=data.get("retry_attempts", 3),
        )


class MCPClient:
    """MCP 客户端

    使用 langchain-mcp-adapters 的 MultiServerMCPClient 连接 MCP 服务器，
    支持多个服务器的工具发现和获取。

    使用示例:
        async with MCPClient(config_path="backend/config/mcp.json") as client:
            tools = await client.get_tools()
    """

    def __init__(
        self,
        config: MCPConfig | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """初始化 MCP 客户端

        Args:
            config: MCP 配置对象
            config_path: 配置文件路径

        Raises:
            MCPClientError: 配置无效或依赖未安装
        """
        if MultiServerMCPClient is None:
            raise MCPClientError(
                "langchain-mcp-adapters 未安装，请运行: pip install langchain-mcp-adapters"
            )

        if config:
            self._config = config
        elif config_path:
            self._config = MCPConfig.from_file(config_path)
        else:
            self._config = MCPConfig()

        self._client: MultiServerMCPClient | None = None
        self._tools: list[Any] = []
        self._connected = False

    def _build_server_params(self) -> dict[str, Any]:
        """构建服务器参数"""
        params: dict[str, Any] = {}

        for server in self._config.mcp_servers:
            if not server.enabled:
                continue

            if server.transport == "stdio" and server.command:
                params[server.name] = StdioServerParameters(
                    command=server.command,
                    args=server.args,
                    env=server.env if server.env else None,
                )
            elif server.transport == "sse" and server.url:
                params[server.name] = {
                    "url": server.url,
                    "transport": "sse",
                }

        return params

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        server_params = self._build_server_params()

        if not server_params:
            raise MCPClientError("没有可用的 MCP 服务器配置")

        self._client = MultiServerMCPClient(server_params)
        self._connected = True

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            self._client = None
        self._connected = False
        self._tools = []

    async def get_tools(self) -> list[Any]:
        """获取所有 MCP 工具

        Returns:
            LangChain 工具列表
        """
        if not self._connected or not self._client:
            raise MCPClientError("客户端未连接，请先调用 connect()")

        if self._tools:
            return self._tools

        self._tools = self._client.get_tools()
        return self._tools

    async def get_tools_by_server(self, server_name: str) -> list[Any]:
        """获取指定服务器的工具

        Args:
            server_name: 服务器名称

        Returns:
            工具列表
        """
        all_tools = await self.get_tools()
        return [t for t in all_tools if hasattr(t, "_server_name") and t._server_name == server_name]

    def list_servers(self) -> list[str]:
        """列出所有已配置的服务器名称"""
        return [s.name for s in self._config.mcp_servers if s.enabled]

    def get_server_config(self, name: str) -> MCPServerConfig | None:
        """获取服务器配置"""
        for server in self._config.mcp_servers:
            if server.name == name:
                return server
        return None

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    async def __aenter__(self) -> "MCPClient":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()


@asynccontextmanager
async def create_mcp_client(
    config_path: str | Path = "backend/config/mcp.json",
) -> Any:
    """创建 MCP 客户端的便捷函数

    Args:
        config_path: 配置文件路径

    Yields:
        MCPClient 实例
    """
    client = MCPClient(config_path=config_path)
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()
