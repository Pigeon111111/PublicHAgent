"""MCP 工具包装器。

把 LangChain MCP 工具包装成项目内部统一的 BaseTool 接口。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.tools.base import BaseTool, ToolError


class MCPToolArgs(BaseModel):
    """MCP 工具通用参数。"""

    pass


class MCPWrappedTool(BaseTool):
    """把 LangChain MCP 工具适配为项目内部工具。"""

    def __init__(self, *, server_name: str, tool: Any) -> None:
        self._server_name = server_name
        self._tool = tool

    @property
    def name(self) -> str:
        raw_name = str(getattr(self._tool, "name", "unknown_mcp_tool"))
        if raw_name.startswith(f"{self._server_name}_"):
            return raw_name
        return f"{self._server_name}_{raw_name}"

    @property
    def description(self) -> str:
        description = str(getattr(self._tool, "description", "")).strip()
        if description:
            return f"{description}（来源: MCP/{self._server_name}）"
        return f"MCP/{self._server_name} 提供的工具"

    @property
    def args_schema(self) -> type[BaseModel]:
        schema = getattr(self._tool, "args_schema", None)
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema
        return MCPToolArgs

    @property
    def capability(self) -> str:
        return f"通过 MCP 服务器 {self._server_name} 调用外部能力。"

    @property
    def limitations(self) -> list[str]:
        return [
            "依赖对应 MCP 服务器可用",
            "执行能力同时受 MCP 服务端和本地 ToolGuard 限制",
        ]

    @property
    def applicable_scenarios(self) -> list[str]:
        return [
            "需要访问文件系统、数据库、浏览器或其他外部系统时",
            "现有内置工具不足以覆盖任务需求时",
        ]

    def run(self, **kwargs: Any) -> Any:
        """MCP 工具默认要求异步调用。"""
        invoke = getattr(self._tool, "invoke", None)
        if not callable(invoke):
            raise ToolError(f"MCP 工具 {self.name} 不支持同步执行")
        return self._normalize_result(invoke(kwargs))

    async def arun(self, **kwargs: Any) -> Any:
        """异步执行 MCP 工具。"""
        ainvoke = getattr(self._tool, "ainvoke", None)
        if callable(ainvoke):
            return self._normalize_result(await ainvoke(kwargs))
        return self.run(**kwargs)

    def _normalize_result(self, result: Any) -> Any:
        """统一 MCP 工具返回格式，便于上层消费。"""
        if isinstance(result, tuple) and len(result) == 2:
            content, artifact = result
            return {
                "content": content,
                "artifact": artifact,
            }
        return result
