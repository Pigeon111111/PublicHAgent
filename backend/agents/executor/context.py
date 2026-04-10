"""Executor 隔离上下文

提供上下文隔离功能，确保 Executor 只获取必要的信息。
"""

from dataclasses import dataclass, field
from typing import Any

from backend.agents.planner.schemas import ExecutionStep


@dataclass
class IsolatedExecutionContext:
    """隔离的执行上下文

    只包含当前步骤执行所需的最小信息集。
    """

    current_step: ExecutionStep
    previous_result: str = ""
    required_output: str = ""
    available_tools: list[str] = field(default_factory=list)
    step_index: int = 0
    total_steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式

        Returns:
            字典格式的上下文
        """
        return {
            "current_step": {
                "step_id": self.current_step.step_id,
                "description": self.current_step.description,
                "tool_name": self.current_step.tool_name,
                "tool_args": self.current_step.tool_args,
                "expected_output": self.current_step.expected_output,
            },
            "previous_result": self.previous_result,
            "required_output": self.required_output,
            "available_tools": self.available_tools,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
        }

    @classmethod
    def create(
        cls,
        plan_steps: list[ExecutionStep],
        step_results: dict[str, str],
        step_index: int,
        available_tools: list[str] | None = None,
    ) -> "IsolatedExecutionContext":
        """从完整状态创建隔离上下文

        Args:
            plan_steps: 计划步骤列表
            step_results: 步骤执行结果字典
            step_index: 当前步骤索引
            available_tools: 可用工具列表

        Returns:
            隔离上下文实例
        """
        if step_index >= len(plan_steps):
            raise ValueError(f"步骤索引 {step_index} 超出范围")

        current_step = plan_steps[step_index]
        previous_result = ""
        if step_index > 0:
            prev_step_id = plan_steps[step_index - 1].step_id
            previous_result = step_results.get(prev_step_id, "")

        return cls(
            current_step=current_step,
            previous_result=previous_result,
            required_output=current_step.expected_output,
            available_tools=available_tools or [],
            step_index=step_index,
            total_steps=len(plan_steps),
        )


class ContextBuilder:
    """上下文构建器

    用于构建隔离的执行上下文。
    """

    def __init__(self) -> None:
        self._plan_steps: list[ExecutionStep] = []
        self._step_results: dict[str, str] = {}
        self._available_tools: list[str] = []

    def set_plan_steps(self, steps: list[ExecutionStep]) -> "ContextBuilder":
        """设置计划步骤

        Args:
            steps: 计划步骤列表

        Returns:
            构建器实例
        """
        self._plan_steps = steps
        return self

    def set_step_results(self, results: dict[str, str]) -> "ContextBuilder":
        """设置步骤结果

        Args:
            results: 步骤执行结果字典

        Returns:
            构建器实例
        """
        self._step_results = results
        return self

    def add_step_result(self, step_id: str, result: str) -> "ContextBuilder":
        """添加单个步骤结果

        Args:
            step_id: 步骤 ID
            result: 执行结果

        Returns:
            构建器实例
        """
        self._step_results[step_id] = result
        return self

    def set_available_tools(self, tools: list[str]) -> "ContextBuilder":
        """设置可用工具

        Args:
            tools: 可用工具列表

        Returns:
            构建器实例
        """
        self._available_tools = tools
        return self

    def build(self, step_index: int) -> IsolatedExecutionContext:
        """构建隔离上下文

        Args:
            step_index: 当前步骤索引

        Returns:
            隔离上下文实例
        """
        return IsolatedExecutionContext.create(
            plan_steps=self._plan_steps,
            step_results=self._step_results,
            step_index=step_index,
            available_tools=self._available_tools,
        )
