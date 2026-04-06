"""MCP 工具集成单元测试"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.mcp.client import (
    MCPClient,
    MCPClientError,
    MCPConfig,
    MCPServerConfig,
)
from backend.tools.mcp.adapter import MCPToolAdapter, adapt_mcp_tool


class TestMCPServerConfig:
    """测试 MCPServerConfig"""

    def test_from_dict_stdio(self) -> None:
        """测试从字典创建 stdio 配置"""
        data = {
            "name": "test_server",
            "command": "npx",
            "args": ["-y", "test-server"],
            "enabled": True,
        }
        config = MCPServerConfig.from_dict(data)
        assert config.name == "test_server"
        assert config.command == "npx"
        assert config.args == ["-y", "test-server"]
        assert config.enabled is True
        assert config.transport == "stdio"

    def test_from_dict_sse(self) -> None:
        """测试从字典创建 SSE 配置"""
        data = {
            "name": "sse_server",
            "url": "http://localhost:8080/sse",
            "transport": "sse",
            "enabled": True,
        }
        config = MCPServerConfig.from_dict(data)
        assert config.name == "sse_server"
        assert config.url == "http://localhost:8080/sse"
        assert config.transport == "sse"

    def test_default_values(self) -> None:
        """测试默认值"""
        config = MCPServerConfig(name="test", command="test")
        assert config.description == ""
        assert config.args == []
        assert config.enabled is True
        assert config.env == {}
        assert config.transport == "stdio"


class TestMCPConfig:
    """测试 MCPConfig"""

    def test_from_file(self, tmp_path: Path) -> None:
        """测试从文件加载配置"""
        config_file = tmp_path / "mcp.json"
        config_data = {
            "mcp_servers": [
                {
                    "name": "server1",
                    "command": "npx",
                    "args": ["-y", "server1"],
                    "enabled": True,
                }
            ],
            "connection_timeout": 60,
            "retry_attempts": 5,
        }
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        config = MCPConfig.from_file(config_file)
        assert len(config.mcp_servers) == 1
        assert config.mcp_servers[0].name == "server1"
        assert config.connection_timeout == 60
        assert config.retry_attempts == 5

    def test_from_file_not_found(self) -> None:
        """测试文件不存在"""
        with pytest.raises(MCPClientError, match="配置文件不存在"):
            MCPConfig.from_file("/nonexistent/path/mcp.json")

    def test_default_values(self) -> None:
        """测试默认值"""
        config = MCPConfig()
        assert config.mcp_servers == []
        assert config.connection_timeout == 30
        assert config.retry_attempts == 3


class TestMCPClient:
    """测试 MCPClient"""

    def test_init_without_deps_raises_error(self) -> None:
        """测试依赖未安装时抛出错误"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient", None):
            with pytest.raises(MCPClientError, match="langchain-mcp-adapters 未安装"):
                MCPClient()

    def test_init_with_config(self) -> None:
        """测试使用配置初始化"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            config = MCPConfig(
                mcp_servers=[
                    MCPServerConfig(name="test", command="test")
                ]
            )
            client = MCPClient(config=config)
            assert client._config == config
            assert not client.is_connected

    def test_list_servers(self) -> None:
        """测试列出服务器"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            config = MCPConfig(
                mcp_servers=[
                    MCPServerConfig(name="server1", command="test", enabled=True),
                    MCPServerConfig(name="server2", command="test", enabled=False),
                ]
            )
            client = MCPClient(config=config)
            servers = client.list_servers()
            assert "server1" in servers
            assert "server2" not in servers

    def test_get_server_config(self) -> None:
        """测试获取服务器配置"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            config = MCPConfig(
                mcp_servers=[
                    MCPServerConfig(name="server1", command="test")
                ]
            )
            client = MCPClient(config=config)
            server_config = client.get_server_config("server1")
            assert server_config is not None
            assert server_config.name == "server1"

    def test_get_server_config_not_found(self) -> None:
        """测试获取不存在的服务器配置"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            client = MCPClient(config=MCPConfig())
            assert client.get_server_config("nonexistent") is None

    def test_connect_no_servers_raises_error(self) -> None:
        """测试没有服务器时连接抛出错误"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            client = MCPClient(config=MCPConfig())
            with pytest.raises(MCPClientError, match="没有可用的 MCP 服务器配置"):
                import asyncio
                asyncio.run(client.connect())

    def test_get_tools_not_connected_raises_error(self) -> None:
        """测试未连接时获取工具抛出错误"""
        with patch("backend.tools.mcp.client.MultiServerMCPClient"):
            client = MCPClient(config=MCPConfig())
            with pytest.raises(MCPClientError, match="客户端未连接"):
                import asyncio
                asyncio.run(client.get_tools())


class TestMCPToolAdapter:
    """测试 MCPToolAdapter"""

    def test_adapt_tool(self) -> None:
        """测试适配工具"""
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "测试工具"
        mock_tool.args_schema = None
        mock_tool.func = lambda x: x

        with patch("backend.tools.mcp.adapter.StructuredTool") as MockStructuredTool:
            mock_structured_tool = MagicMock()
            MockStructuredTool.return_value = mock_structured_tool

            result = MCPToolAdapter.adapt_tool(mock_tool)
            assert result == mock_structured_tool

    def test_adapt_tools(self) -> None:
        """测试批量适配工具"""
        mock_tools = [MagicMock(name=f"tool{i}") for i in range(3)]
        for i, tool in enumerate(mock_tools):
            tool.name = f"tool{i}"
            tool.description = f"工具{i}"
            tool.args_schema = None
            tool.func = lambda x: x

        with patch("backend.tools.mcp.adapter.StructuredTool"):
            results = MCPToolAdapter.adapt_tools(mock_tools)
            assert len(results) == 3


class TestAdaptMCPTool:
    """测试便捷函数"""

    def test_adapt_mcp_tool(self) -> None:
        """测试 adapt_mcp_tool 函数"""
        mock_tool = MagicMock()
        mock_tool.name = "test"
        mock_tool.description = "test"
        mock_tool.args_schema = None

        with patch("backend.tools.mcp.adapter.MCPToolAdapter.adapt_tool") as mock_adapt:
            adapt_mcp_tool(mock_tool)
            mock_adapt.assert_called_once_with(mock_tool)
