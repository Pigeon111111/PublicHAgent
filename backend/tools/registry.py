"""工具注册表模块

实现工具的注册、注销、查询等功能。
"""

from typing import Any

from backend.tools.base import BaseTool, ToolError


class ToolRegistry:
    """工具注册表

    支持工具的注册、注销、查询，以及获取 OpenAI 格式的工具定义。
    """

    def __init__(self) -> None:
        """初始化工具注册表"""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具

        Args:
            tool: 工具实例

        Raises:
            ToolError: 工具已存在
        """
        if tool.name in self._tools:
            raise ToolError(f"工具已存在: {tool.name}")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """注销工具

        Args:
            name: 工具名称

        Raises:
            ToolError: 工具不存在
        """
        if name not in self._tools:
            raise ToolError(f"工具不存在: {name}")
        del self._tools[name]

    def get(self, name: str) -> BaseTool:
        """获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例

        Raises:
            ToolError: 工具不存在
        """
        if name not in self._tools:
            raise ToolError(f"工具不存在: {name}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        """检查工具是否存在

        Args:
            name: 工具名称

        Returns:
            是否存在
        """
        return name in self._tools

    def list_tools(self) -> list[str]:
        """列出所有工具名称

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def get_all_tools(self) -> list[BaseTool]:
        """获取所有工具

        Returns:
            工具列表
        """
        return list(self._tools.values())

    def get_openai_tools_definition(self) -> list[dict[str, Any]]:
        """获取所有工具的 OpenAI 格式定义

        Returns:
            OpenAI 工具定义列表
        """
        return [tool.get_openai_tool_definition() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> Any:
        """执行工具

        Args:
            name: 工具名称
            **kwargs: 工具参数

        Returns:
            执行结果

        Raises:
            ToolError: 工具不存在或执行失败
        """
        tool = self.get(name)
        validated_args = tool.validate_args(**kwargs)
        return tool.run(**validated_args.model_dump())

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()


# 全局工具注册表实例
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表

    Returns:
        工具注册表实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> None:
    """重置全局工具注册表"""
    global _global_registry
    _global_registry = None
