"""LangGraph 工作流模块

使用 LangGraph 构建多智能体工作流，实现计划-执行-反思循环。
"""

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from backend.agents.base.llm_client import LLMClient
from backend.agents.intent.recognizer import IntentRecognizer
from backend.core.state import (
    AgentState,
    create_execution_step,
    create_initial_state,
    create_plan,
)


class PlanStep(BaseModel):
    """计划步骤"""

    step_id: str = Field(description="步骤唯一标识")
    action: str = Field(description="动作描述")
    tool_name: str = Field(description="使用的工具名称", default="")
    tool_args: dict[str, Any] = Field(description="工具参数", default_factory=dict)


class PlanResult(BaseModel):
    """计划结果"""

    steps: list[PlanStep] = Field(description="执行步骤列表")
    reasoning: str = Field(description="计划推理过程")


class ReflectionResult(BaseModel):
    """反思结果"""

    success: bool = Field(description="执行是否成功")
    feedback: str = Field(description="反馈意见")
    should_replan: bool = Field(description="是否需要重新规划")
    suggestions: list[str] = Field(description="改进建议", default_factory=list)


class AgentWorkflow:
    """Agent 工作流

    使用 LangGraph 构建计划-执行-反思循环工作流。
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        intent_recognizer: IntentRecognizer | None = None,
    ) -> None:
        """初始化工作流

        Args:
            llm: LLM 实例
            intent_recognizer: 意图识别器实例
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._intent_recognizer = intent_recognizer
        self._workflow: StateGraph | None = None
        self._compiled_workflow: Any = None
        self._checkpointer = MemorySaver()

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_default_llm()

    def _get_intent_recognizer(self) -> IntentRecognizer:
        """获取意图识别器实例"""
        if self._intent_recognizer is None:
            self._intent_recognizer = IntentRecognizer(self._get_llm())
        return self._intent_recognizer

    async def _intent_node(self, state: AgentState) -> dict[str, Any]:
        """意图识别节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        recognizer = self._get_intent_recognizer()
        result = await recognizer.recognize(state["user_query"])

        return {
            "intent": result.intent,
            "intent_confidence": result.confidence,
            "messages": [
                AIMessage(content=f"识别到意图: {result.intent}，置信度: {result.confidence:.2f}")
            ],
        }

    async def _planner_node(self, state: AgentState) -> dict[str, Any]:
        """计划节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        llm = self._get_llm()

        system_prompt = """你是一个公共卫生数据分析专家。根据用户的查询和识别的意图，制定详细的执行计划。

请将任务分解为具体的执行步骤，每个步骤应包含：
1. step_id: 步骤唯一标识（如 "step_1", "step_2"）
2. action: 动作描述
3. tool_name: 需要使用的工具名称（可选）
4. tool_args: 工具参数（可选）

确保计划合理、可执行，并能够解决用户的问题。"""

        user_message = f"""用户查询: {state['user_query']}
识别意图: {state['intent']}
已执行步骤数: {len(state['execution_results'])}
反思反馈: {state['reflection_feedback'] or '无'}

请制定执行计划。"""

        structured_llm = llm.with_structured_output(PlanResult)
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        if not isinstance(result, PlanResult):
            return {
                "plan": create_plan([]),
                "should_replan": False,
                "messages": [AIMessage(content="计划生成失败")],
            }

        steps = [
            create_execution_step(
                step_id=step.step_id,
                action=step.action,
                tool_name=step.tool_name,
                tool_args=step.tool_args,
            )
            for step in result.steps
        ]

        plan = create_plan(steps)

        return {
            "plan": plan,
            "should_replan": False,
            "messages": [
                AIMessage(content=f"已制定计划，共 {len(steps)} 个步骤:\n{result.reasoning}")
            ],
        }

    async def _executor_node(self, state: AgentState) -> dict[str, Any]:
        """执行节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        plan = state["plan"]
        if plan is None:
            return {
                "messages": [AIMessage(content="没有可执行的计划")],
            }

        current_index = plan["current_step_index"]
        if current_index >= plan["total_steps"]:
            return {
                "messages": [AIMessage(content="所有步骤已执行完成")],
            }

        current_step = plan["steps"][current_index]
        current_step["status"] = "running"

        try:
            result = f"模拟执行: {current_step['action']}"
            current_step["result"] = result
            current_step["status"] = "completed"
        except Exception as e:
            current_step["status"] = "failed"
            current_step["error"] = str(e)

        new_results = state["execution_results"] + [current_step]
        new_plan = {
            **plan,
            "current_step_index": current_index + 1,
        }

        return {
            "plan": new_plan,
            "current_step": current_step,
            "execution_results": new_results,
            "iteration_count": state["iteration_count"] + 1,
            "messages": [
                AIMessage(content=f"执行步骤 {current_step['step_id']}: {current_step['action']} - {current_step['status']}")
            ],
        }

    async def _reflection_node(self, state: AgentState) -> dict[str, Any]:
        """反思节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        llm = self._get_llm()

        system_prompt = """你是一个质量评估专家。请评估执行结果，判断是否成功解决了用户的问题。

评估要点：
1. 执行步骤是否完整
2. 结果是否符合预期
3. 是否需要重新规划
4. 有哪些改进建议"""

        execution_summary = "\n".join([
            f"- {step['step_id']}: {step['action']} ({step['status']})"
            for step in state["execution_results"]
        ])

        user_message = f"""用户查询: {state['user_query']}
执行步骤:
{execution_summary}

请评估执行结果。"""

        structured_llm = llm.with_structured_output(ReflectionResult)
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        if not isinstance(result, ReflectionResult):
            return {
                "reflection_feedback": "反思失败",
                "should_replan": False,
                "messages": [AIMessage(content="反思评估失败")],
            }

        return {
            "reflection_feedback": result.feedback,
            "should_replan": result.should_replan,
            "messages": [
                AIMessage(content=f"反思结果: {'成功' if result.success else '需要改进'}\n反馈: {result.feedback}")
            ],
        }

    def _should_continue(self, state: AgentState) -> Literal["continue", "replan", "end"]:
        """判断是否继续执行

        Args:
            state: 当前状态

        Returns:
            下一步动作
        """
        if state["iteration_count"] >= state["max_iterations"]:
            return "end"

        if state["should_replan"]:
            return "replan"

        plan = state["plan"]
        if plan is None:
            return "end"

        if plan["current_step_index"] >= plan["total_steps"]:
            return "end"

        return "continue"

    def _should_replan_after_reflection(
        self, state: AgentState
    ) -> Literal["replan", "end"]:
        """反思后判断是否重新规划

        Args:
            state: 当前状态

        Returns:
            下一步动作
        """
        if state["should_replan"] and state["iteration_count"] < state["max_iterations"]:
            return "replan"
        return "end"

    def build_workflow(self) -> StateGraph:
        """构建工作流图

        Returns:
            工作流图
        """
        workflow = StateGraph(AgentState)

        workflow.add_node("intent", self._intent_node)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("executor", self._executor_node)
        workflow.add_node("reflection", self._reflection_node)

        workflow.set_entry_point("intent")
        workflow.add_edge("intent", "planner")
        workflow.add_edge("planner", "executor")

        workflow.add_conditional_edges(
            "executor",
            self._should_continue,
            {
                "continue": "executor",
                "replan": "planner",
                "end": "reflection",
            },
        )

        workflow.add_conditional_edges(
            "reflection",
            self._should_replan_after_reflection,
            {
                "replan": "planner",
                "end": END,
            },
        )

        self._workflow = workflow
        return workflow

    def compile(self) -> Any:
        """编译工作流

        Returns:
            编译后的工作流
        """
        if self._workflow is None:
            self.build_workflow()

        assert self._workflow is not None
        self._compiled_workflow = self._workflow.compile(checkpointer=self._checkpointer)
        return self._compiled_workflow

    async def run(self, user_query: str, thread_id: str = "default") -> AgentState:
        """运行工作流

        Args:
            user_query: 用户查询
            thread_id: 线程 ID（用于状态持久化）

        Returns:
            最终状态
        """
        if self._compiled_workflow is None:
            self.compile()

        assert self._compiled_workflow is not None
        initial_state = create_initial_state(user_query)
        config = {"configurable": {"thread_id": thread_id}}

        result = await self._compiled_workflow.ainvoke(initial_state, config)
        return result  # type: ignore[return-value,no-any-return]

    def get_workflow_graph(self) -> str:
        """获取工作流图的 ASCII 表示

        Returns:
            ASCII 图形
        """
        if self._compiled_workflow is None:
            self.compile()

        try:
            return str(self._compiled_workflow.get_graph().draw_ascii())
        except Exception:
            return "无法生成图形"


def create_workflow(
    llm: BaseChatModel | None = None,
    intent_recognizer: IntentRecognizer | None = None,
) -> AgentWorkflow:
    """创建工作流实例

    Args:
        llm: LLM 实例
        intent_recognizer: 意图识别器实例

    Returns:
        工作流实例
    """
    return AgentWorkflow(llm=llm, intent_recognizer=intent_recognizer)
