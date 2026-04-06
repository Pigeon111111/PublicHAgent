"""Planner Agent 结构化输出格式

使用 Pydantic 定义计划生成相关的数据结构。
"""

from typing import Any

from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """执行步骤"""

    step_id: str = Field(description="步骤唯一标识，如 step_1, step_2")
    description: str = Field(description="步骤描述")
    tool_name: str = Field(description="使用的工具名称", default="")
    tool_args: dict[str, Any] = Field(description="工具参数", default_factory=dict)
    dependencies: list[str] = Field(description="依赖的步骤 ID 列表", default_factory=list)
    expected_output: str = Field(description="预期输出描述", default="")


class ExecutionPlan(BaseModel):
    """执行计划"""

    steps: list[ExecutionStep] = Field(description="执行步骤列表")
    reasoning: str = Field(description="计划推理过程")
    estimated_complexity: str = Field(description="预估复杂度: low/medium/high", default="medium")


class ReplanRequest(BaseModel):
    """重新规划请求"""

    original_plan: ExecutionPlan = Field(description="原始计划")
    failed_steps: list[str] = Field(description="失败的步骤 ID 列表")
    feedback: str = Field(description="反思反馈")
    context: dict[str, Any] = Field(description="额外上下文", default_factory=dict)


class ToolSelection(BaseModel):
    """工具选择结果"""

    tool_name: str = Field(description="选择的工具名称")
    tool_args: dict[str, Any] = Field(description="工具参数")
    reasoning: str = Field(description="选择理由")
