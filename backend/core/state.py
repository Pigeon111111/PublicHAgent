"""LangGraph 工作流状态定义

使用 TypedDict 定义 Agent 工作流的状态结构。
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ExecutionStep(TypedDict):
    """执行步骤"""

    step_id: str
    action: str
    tool_name: str
    tool_args: dict[str, Any]
    result: Any
    status: str
    error: str | None


class Plan(TypedDict):
    """执行计划"""

    steps: list[ExecutionStep]
    current_step_index: int
    total_steps: int


class AgentState(TypedDict):
    """Agent 工作流状态

    使用 TypedDict 定义状态结构，支持 LangGraph 的状态管理。
    """

    user_query: str
    user_context: dict[str, Any]
    session_id: str
    intent: str
    intent_confidence: float
    plan: Plan | None
    current_step: ExecutionStep | None
    execution_results: list[ExecutionStep]
    reflection_feedback: str
    should_replan: bool
    final_result: str
    messages: Annotated[list[Any], add_messages]
    iteration_count: int
    max_iterations: int
    workspace: dict[str, Any]
    plan_model: Any
    executor_results: list[Any]
    trajectory_id: str
    learned_skill: str | None


def create_initial_state(
    user_query: str,
    user_context: dict[str, Any] | None = None,
    session_id: str = "default",
) -> AgentState:
    """创建初始状态

    Args:
        user_query: 用户查询

    Returns:
        初始状态字典
    """
    return AgentState(
        user_query=user_query,
        user_context=user_context or {},
        session_id=session_id,
        intent="",
        intent_confidence=0.0,
        plan=None,
        current_step=None,
        execution_results=[],
        reflection_feedback="",
        should_replan=False,
        final_result="",
        messages=[],
        iteration_count=0,
        max_iterations=10,
        workspace={},
        plan_model=None,
        executor_results=[],
        trajectory_id="",
        learned_skill=None,
    )


def create_execution_step(
    step_id: str,
    action: str,
    tool_name: str = "",
    tool_args: dict[str, Any] | None = None,
    result: Any = None,
    status: str = "pending",
    error: str | None = None,
) -> ExecutionStep:
    """创建执行步骤

    Args:
        step_id: 步骤 ID
        action: 动作描述
        tool_name: 工具名称
        tool_args: 工具参数
        result: 执行结果
        status: 状态
        error: 错误信息

    Returns:
        执行步骤字典
    """
    return ExecutionStep(
        step_id=step_id,
        action=action,
        tool_name=tool_name,
        tool_args=tool_args or {},
        result=result,
        status=status,
        error=error,
    )


def create_plan(steps: list[ExecutionStep]) -> Plan:
    """创建执行计划

    Args:
        steps: 执行步骤列表

    Returns:
        执行计划字典
    """
    return Plan(
        steps=steps,
        current_step_index=0,
        total_steps=len(steps),
    )
