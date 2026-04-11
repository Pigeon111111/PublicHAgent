"""工具基础模块

定义工具的标准接口和抽象基类。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolError(Exception):
    """工具错误"""

    pass


class BaseTool(ABC):
    """工具抽象基类

    所有工具必须继承此类并实现以下方法：
    - name: 工具名称
    - description: 工具描述
    - args_schema: 参数 Schema
    - run: 执行方法
    - capability: 能力范围描述
    - limitations: 限制条件
    - applicable_scenarios: 适用场景
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def args_schema(self) -> type[BaseModel]:
        """参数 Schema（Pydantic BaseModel）"""
        pass

    @property
    def capability(self) -> str:
        """能力范围描述

        描述该工具能够完成什么类型的任务，以及它的核心能力边界。
        子类应该重写此属性以提供具体的能力描述。
        """
        return "基础工具能力"

    @property
    def limitations(self) -> list[str]:
        """限制条件

        描述该工具不能做什么，或者使用时需要注意的限制。
        子类应该重写此属性以提供具体的限制条件。
        """
        return []

    @property
    def applicable_scenarios(self) -> list[str]:
        """适用场景

        描述该工具最适合在什么场景下使用。
        子类应该重写此属性以提供具体的适用场景。
        """
        return []

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        pass

    async def arun(self, **kwargs: Any) -> Any:
        """异步执行工具。

        默认将同步工具放入线程池，便于统一接入异步工具。
        """
        return await asyncio.to_thread(self.run, **kwargs)

    def get_openai_tool_definition(self) -> dict[str, Any]:
        """获取 OpenAI 格式的工具定义

        Returns:
            OpenAI 工具定义字典
        """
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }

    def validate_args(self, **kwargs: Any) -> BaseModel:
        """验证参数

        Args:
            **kwargs: 工具参数

        Returns:
            验证后的参数对象

        Raises:
            ToolError: 参数验证失败
        """
        try:
            return self.args_schema(**kwargs)
        except Exception as e:
            raise ToolError(f"参数验证失败: {e}") from e
