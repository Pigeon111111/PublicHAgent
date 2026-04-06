"""LangGraph 工作流集成测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.intent.recognizer import IntentResult
from backend.core.state import (
    AgentState,
    create_execution_step,
    create_initial_state,
    create_plan,
)
from backend.core.workflow import (
    AgentWorkflow,
    PlanResult,
    PlanStep,
    ReflectionResult,
    create_workflow,
)


class TestStateFunctions:
    """测试状态函数"""

    def test_create_initial_state(self) -> None:
        """测试创建初始状态"""
        state = create_initial_state("测试查询")
        assert state["user_query"] == "测试查询"
        assert state["intent"] == ""
        assert state["intent_confidence"] == 0.0
        assert state["plan"] is None
        assert state["execution_results"] == []
        assert state["should_replan"] is False
        assert state["iteration_count"] == 0
        assert state["max_iterations"] == 10

    def test_create_execution_step(self) -> None:
        """测试创建执行步骤"""
        step = create_execution_step(
            step_id="step_1",
            action="测试动作",
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
        )
        assert step["step_id"] == "step_1"
        assert step["action"] == "测试动作"
        assert step["tool_name"] == "test_tool"
        assert step["tool_args"] == {"arg1": "value1"}
        assert step["status"] == "pending"
        assert step["result"] is None
        assert step["error"] is None

    def test_create_plan(self) -> None:
        """测试创建执行计划"""
        steps = [
            create_execution_step(step_id="step_1", action="步骤1"),
            create_execution_step(step_id="step_2", action="步骤2"),
        ]
        plan = create_plan(steps)
        assert plan["total_steps"] == 2
        assert plan["current_step_index"] == 0
        assert len(plan["steps"]) == 2


class TestPlanStep:
    """测试计划步骤模型"""

    def test_plan_step_creation(self) -> None:
        """测试创建计划步骤"""
        step = PlanStep(
            step_id="step_1",
            action="测试动作",
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
        )
        assert step.step_id == "step_1"
        assert step.action == "测试动作"
        assert step.tool_name == "test_tool"
        assert step.tool_args == {"arg1": "value1"}


class TestPlanResult:
    """测试计划结果模型"""

    def test_plan_result_creation(self) -> None:
        """测试创建计划结果"""
        steps = [
            PlanStep(step_id="step_1", action="步骤1"),
            PlanStep(step_id="step_2", action="步骤2"),
        ]
        result = PlanResult(steps=steps, reasoning="测试推理")
        assert len(result.steps) == 2
        assert result.reasoning == "测试推理"


class TestReflectionResult:
    """测试反思结果模型"""

    def test_reflection_result_creation(self) -> None:
        """测试创建反思结果"""
        result = ReflectionResult(
            success=True,
            feedback="执行成功",
            should_replan=False,
            suggestions=["建议1", "建议2"],
        )
        assert result.success is True
        assert result.feedback == "执行成功"
        assert result.should_replan is False
        assert len(result.suggestions) == 2


class TestAgentWorkflow:
    """测试 Agent 工作流"""

    def test_init_without_llm(self) -> None:
        """测试不带 LLM 初始化"""
        workflow = AgentWorkflow()
        assert workflow._llm is None
        assert workflow._llm_client is None
        assert workflow._workflow is None

    def test_init_with_llm(self) -> None:
        """测试带 LLM 初始化"""
        mock_llm = MagicMock()
        workflow = AgentWorkflow(llm=mock_llm)
        assert workflow._llm == mock_llm

    def test_build_workflow(self) -> None:
        """测试构建工作流"""
        workflow = AgentWorkflow()
        graph = workflow.build_workflow()
        assert graph is not None
        assert workflow._workflow is not None

    def test_compile(self) -> None:
        """测试编译工作流"""
        workflow = AgentWorkflow()
        compiled = workflow.compile()
        assert compiled is not None
        assert workflow._compiled_workflow is not None

    def test_get_workflow_graph(self) -> None:
        """测试获取工作流图形"""
        workflow = AgentWorkflow()
        graph_str = workflow.get_workflow_graph()
        assert isinstance(graph_str, str)


class TestWorkflowNodes:
    """测试工作流节点"""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """创建 Mock LLM"""
        mock = MagicMock()

        intent_structured = AsyncMock()
        intent_structured.ainvoke = AsyncMock(return_value=IntentResult(
            intent="descriptive_analysis",
            confidence=0.85,
            reason="测试意图识别",
        ))

        plan_structured = AsyncMock()
        plan_structured.ainvoke = AsyncMock(return_value=PlanResult(
            steps=[
                PlanStep(step_id="step_1", action="分析数据"),
            ],
            reasoning="测试计划",
        ))

        reflection_structured = AsyncMock()
        reflection_structured.ainvoke = AsyncMock(return_value=ReflectionResult(
            success=True,
            feedback="执行成功",
            should_replan=False,
        ))

        def mock_with_structured_output(model_class):
            if model_class == IntentResult:
                return intent_structured
            elif model_class == PlanResult:
                return plan_structured
            elif model_class == ReflectionResult:
                return reflection_structured
            return plan_structured

        mock.with_structured_output = MagicMock(side_effect=mock_with_structured_output)

        return mock

    @pytest.mark.asyncio
    async def test_intent_node(self, mock_llm: MagicMock) -> None:
        """测试意图识别节点"""
        workflow = AgentWorkflow(llm=mock_llm)
        state = create_initial_state("计算均值和标准差")

        result = await workflow._intent_node(state)

        assert "intent" in result
        assert result["intent"] == "descriptive_analysis"
        assert result["intent_confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_planner_node(self, mock_llm: MagicMock) -> None:
        """测试计划节点"""
        workflow = AgentWorkflow(llm=mock_llm)
        state = create_initial_state("测试查询")
        state["intent"] = "descriptive_analysis"

        result = await workflow._planner_node(state)

        assert "plan" in result
        assert result["plan"] is not None
        assert result["plan"]["total_steps"] >= 1

    @pytest.mark.asyncio
    async def test_executor_node(self, mock_llm: MagicMock) -> None:
        """测试执行节点"""
        workflow = AgentWorkflow(llm=mock_llm)
        state = create_initial_state("测试查询")
        state["plan"] = create_plan([
            create_execution_step(step_id="step_1", action="步骤1"),
        ])

        result = await workflow._executor_node(state)

        assert "execution_results" in result
        assert len(result["execution_results"]) == 1
        assert result["execution_results"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_reflection_node(self, mock_llm: MagicMock) -> None:
        """测试反思节点"""
        workflow = AgentWorkflow(llm=mock_llm)
        state = create_initial_state("测试查询")
        state["execution_results"] = [
            create_execution_step(step_id="step_1", action="步骤1", status="completed"),
        ]

        result = await workflow._reflection_node(state)

        assert "reflection_feedback" in result
        assert "should_replan" in result


class TestWorkflowRouting:
    """测试工作流路由"""

    def test_should_continue_end_by_iterations(self) -> None:
        """测试达到最大迭代次数结束"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["iteration_count"] = 10
        state["max_iterations"] = 10

        result = workflow._should_continue(state)
        assert result == "end"

    def test_should_continue_replan(self) -> None:
        """测试需要重新规划"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["should_replan"] = True
        state["iteration_count"] = 0
        state["max_iterations"] = 10

        result = workflow._should_continue(state)
        assert result == "replan"

    def test_should_continue_continue(self) -> None:
        """测试继续执行"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["plan"] = create_plan([
            create_execution_step(step_id="step_1", action="步骤1"),
            create_execution_step(step_id="step_2", action="步骤2"),
        ])
        state["plan"]["current_step_index"] = 0
        state["should_replan"] = False
        state["iteration_count"] = 0
        state["max_iterations"] = 10

        result = workflow._should_continue(state)
        assert result == "continue"

    def test_should_continue_end_by_completion(self) -> None:
        """测试所有步骤完成结束"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["plan"] = create_plan([
            create_execution_step(step_id="step_1", action="步骤1"),
        ])
        state["plan"]["current_step_index"] = 1
        state["should_replan"] = False
        state["iteration_count"] = 0
        state["max_iterations"] = 10

        result = workflow._should_continue(state)
        assert result == "end"

    def test_should_replan_after_reflection_replan(self) -> None:
        """测试反思后重新规划"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["should_replan"] = True
        state["iteration_count"] = 0
        state["max_iterations"] = 10

        result = workflow._should_replan_after_reflection(state)
        assert result == "replan"

    def test_should_replan_after_reflection_end(self) -> None:
        """测试反思后结束"""
        workflow = AgentWorkflow()
        state = create_initial_state("测试查询")
        state["should_replan"] = False
        state["iteration_count"] = 0
        state["max_iterations"] = 10

        result = workflow._should_replan_after_reflection(state)
        assert result == "end"


class TestWorkflowIntegration:
    """测试工作流集成"""

    @pytest.fixture
    def mock_llm_with_intent(self) -> MagicMock:
        """创建支持意图识别的 Mock LLM"""
        mock = MagicMock()

        intent_structured = AsyncMock()
        intent_structured.ainvoke = AsyncMock(return_value=IntentResult(
            intent="descriptive_analysis",
            confidence=0.85,
            reason="测试意图识别",
        ))

        plan_structured = AsyncMock()
        plan_structured.ainvoke = AsyncMock(return_value=PlanResult(
            steps=[
                PlanStep(step_id="step_1", action="分析数据"),
                PlanStep(step_id="step_2", action="生成报告"),
            ],
            reasoning="测试计划",
        ))

        reflection_structured = AsyncMock()
        reflection_structured.ainvoke = AsyncMock(return_value=ReflectionResult(
            success=True,
            feedback="执行成功",
            should_replan=False,
        ))

        def mock_with_structured_output(model_class):
            if model_class == IntentResult:
                return intent_structured
            elif model_class == PlanResult:
                return plan_structured
            elif model_class == ReflectionResult:
                return reflection_structured
            return plan_structured

        mock.with_structured_output = MagicMock(side_effect=mock_with_structured_output)
        return mock

    @pytest.mark.asyncio
    async def test_workflow_run_basic(self, mock_llm_with_intent: MagicMock) -> None:
        """测试基本工作流运行"""
        workflow = AgentWorkflow(llm=mock_llm_with_intent)
        workflow.compile()

        result = await workflow.run("计算均值和标准差")

        assert result["intent"] == "descriptive_analysis"
        assert result["intent_confidence"] >= 0.7
        assert len(result["execution_results"]) > 0

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self, mock_llm_with_intent: MagicMock) -> None:
        """测试状态持久化"""
        workflow = AgentWorkflow(llm=mock_llm_with_intent)
        workflow.compile()

        result1 = await workflow.run("测试查询1", thread_id="thread_1")
        result2 = await workflow.run("测试查询2", thread_id="thread_2")

        assert result1["user_query"] == "测试查询1"
        assert result2["user_query"] == "测试查询2"


class TestCreateWorkflow:
    """测试工作流工厂函数"""

    def test_create_workflow_default(self) -> None:
        """测试使用默认参数创建工作流"""
        workflow = create_workflow()
        assert isinstance(workflow, AgentWorkflow)
        assert workflow._llm is None

    def test_create_workflow_with_llm(self) -> None:
        """测试带 LLM 创建工作流"""
        mock_llm = MagicMock()
        workflow = create_workflow(llm=mock_llm)
        assert workflow._llm == mock_llm


class TestIntentRecognitionIntegration:
    """测试意图识别与工作流集成"""

    @pytest.mark.asyncio
    async def test_intent_recognition_in_workflow(self) -> None:
        """测试工作流中的意图识别"""
        mock_llm = MagicMock()

        intent_structured = AsyncMock()
        intent_structured.ainvoke = AsyncMock(return_value=IntentResult(
            intent="descriptive_analysis",
            confidence=0.85,
            reason="测试意图识别",
        ))

        plan_structured = AsyncMock()
        plan_structured.ainvoke = AsyncMock(return_value=PlanResult(
            steps=[PlanStep(step_id="step_1", action="分析")],
            reasoning="测试",
        ))

        reflection_structured = AsyncMock()
        reflection_structured.ainvoke = AsyncMock(return_value=ReflectionResult(
            success=True,
            feedback="成功",
            should_replan=False,
        ))

        def mock_with_structured_output(model_class):
            if model_class == IntentResult:
                return intent_structured
            elif model_class == PlanResult:
                return plan_structured
            return reflection_structured

        mock_llm.with_structured_output = MagicMock(side_effect=mock_with_structured_output)

        workflow = AgentWorkflow(llm=mock_llm)
        workflow.compile()

        test_queries = [
            ("计算均值", "descriptive_analysis"),
            ("进行t检验", "statistical_test"),
            ("绘制柱状图", "visualization"),
        ]

        for query, expected_intent in test_queries:
            result = await workflow.run(query)
            assert result["intent"] == expected_intent
