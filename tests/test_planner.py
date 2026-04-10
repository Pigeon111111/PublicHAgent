"""Planner Agent 单元测试"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.planner import ExecutionPlan, ExecutionStep, PlannerAgent
from backend.agents.planner.schemas import ReplanRequest, ToolSelection


class TestExecutionStep:
    """测试执行步骤模型"""

    def test_execution_step_creation(self) -> None:
        """测试创建执行步骤"""
        step = ExecutionStep(
            step_id="step_1",
            description="读取数据文件",
            tool_name="read_file",
            tool_args={"file_path": "data.csv"},
            dependencies=[],
            expected_output="文件内容",
        )
        assert step.step_id == "step_1"
        assert step.description == "读取数据文件"
        assert step.tool_name == "read_file"
        assert step.tool_args == {"file_path": "data.csv"}
        assert step.dependencies == []
        assert step.expected_output == "文件内容"

    def test_execution_step_defaults(self) -> None:
        """测试执行步骤默认值"""
        step = ExecutionStep(
            step_id="step_1",
            description="测试步骤",
        )
        assert step.tool_name == ""
        assert step.tool_args == {}
        assert step.dependencies == []
        assert step.expected_output == ""


class TestExecutionPlan:
    """测试执行计划模型"""

    def test_execution_plan_creation(self) -> None:
        """测试创建执行计划"""
        steps = [
            ExecutionStep(step_id="step_1", description="步骤1"),
            ExecutionStep(step_id="step_2", description="步骤2"),
        ]
        plan = ExecutionPlan(
            steps=steps,
            reasoning="测试推理",
            estimated_complexity="low",
        )
        assert len(plan.steps) == 2
        assert plan.reasoning == "测试推理"
        assert plan.estimated_complexity == "low"


class TestPlannerAgent:
    """测试 Planner Agent"""

    def test_init_without_llm(self) -> None:
        """测试不带 LLM 初始化"""
        agent = PlannerAgent()
        assert agent._llm is None
        assert agent._llm_client is None

    def test_init_with_llm(self) -> None:
        """测试带 LLM 初始化"""
        mock_llm = MagicMock()
        agent = PlannerAgent(llm=mock_llm)
        assert agent._llm == mock_llm

    def test_validate_plan_empty(self) -> None:
        """测试验证空计划"""
        agent = PlannerAgent()
        plan = ExecutionPlan(steps=[], reasoning="空计划")
        is_valid, errors = agent.validate_plan(plan)
        assert is_valid is False
        assert "计划没有步骤" in errors

    def test_validate_plan_valid(self) -> None:
        """测试验证有效计划"""
        agent = PlannerAgent()
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="步骤1"),
                ExecutionStep(step_id="step_2", description="步骤2", dependencies=["step_1"]),
            ],
            reasoning="有效计划",
        )
        is_valid, errors = agent.validate_plan(plan)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_plan_circular_dependency(self) -> None:
        """测试验证循环依赖"""
        agent = PlannerAgent()
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="步骤1", dependencies=["step_2"]),
                ExecutionStep(step_id="step_2", description="步骤2", dependencies=["step_1"]),
            ],
            reasoning="循环依赖计划",
        )
        is_valid, errors = agent.validate_plan(plan)
        assert is_valid is False
        assert any("循环依赖" in e for e in errors)

    def test_validate_plan_missing_dependency(self) -> None:
        """测试验证缺失依赖"""
        agent = PlannerAgent()
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="步骤1", dependencies=["step_0"]),
            ],
            reasoning="缺失依赖计划",
        )
        is_valid, errors = agent.validate_plan(plan)
        assert is_valid is False
        assert any("依赖不存在的步骤" in e for e in errors)

    def test_get_next_step(self) -> None:
        """测试获取下一个步骤"""
        agent = PlannerAgent()
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="步骤1"),
                ExecutionStep(step_id="step_2", description="步骤2", dependencies=["step_1"]),
                ExecutionStep(step_id="step_3", description="步骤3"),
            ],
            reasoning="测试计划",
        )

        step = agent.get_next_step(plan, set())
        assert step is not None
        assert step.step_id in ["step_1", "step_3"]

        step = agent.get_next_step(plan, {"step_1"})
        assert step is not None
        assert step.step_id == "step_2"

        step = agent.get_next_step(plan, {"step_1", "step_2", "step_3"})
        assert step is None

    def test_get_plan_summary(self) -> None:
        """测试获取计划摘要"""
        agent = PlannerAgent()
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="步骤1"),
            ],
            reasoning="测试推理",
            estimated_complexity="low",
        )
        summary = agent.get_plan_summary(plan)
        assert "步骤数: 1" in summary
        assert "复杂度: low" in summary
        assert "step_1" in summary


class TestPlannerAgentAsync:
    """测试 Planner Agent 异步方法"""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """创建 Mock LLM"""
        mock = MagicMock()

        plan_structured = AsyncMock()
        plan_structured.ainvoke = AsyncMock(return_value=ExecutionPlan(
            steps=[
                ExecutionStep(step_id="step_1", description="读取数据"),
                ExecutionStep(step_id="step_2", description="分析数据"),
            ],
            reasoning="测试计划",
            estimated_complexity="medium",
        ))

        tool_structured = AsyncMock()
        tool_structured.ainvoke = AsyncMock(return_value=ToolSelection(
            tool_name="read_file",
            tool_args={"file_path": "data.csv"},
            reasoning="需要读取文件",
        ))

        def mock_with_structured_output(model_class):
            if model_class == ExecutionPlan:
                return plan_structured
            elif model_class == ToolSelection:
                return tool_structured
            return plan_structured

        mock.with_structured_output = MagicMock(side_effect=mock_with_structured_output)
        return mock

    @pytest.mark.asyncio
    async def test_create_plan(self, mock_llm: MagicMock) -> None:
        """测试创建计划"""
        agent = PlannerAgent(llm=mock_llm)
        plan = await agent.create_plan(
            user_query="分析数据",
            intent="descriptive_analysis",
        )
        assert len(plan.steps) == 2
        assert plan.steps[0].step_id == "step_1"

    @pytest.mark.asyncio
    async def test_replan(self, mock_llm: MagicMock) -> None:
        """测试重新规划"""
        agent = PlannerAgent(llm=mock_llm)
        original_plan = ExecutionPlan(
            steps=[ExecutionStep(step_id="step_1", description="原始步骤")],
            reasoning="原始计划",
        )
        request = ReplanRequest(
            original_plan=original_plan,
            failed_steps=["step_1"],
            feedback="执行失败",
        )
        new_plan = await agent.replan(request)
        assert len(new_plan.steps) == 2

    @pytest.mark.asyncio
    async def test_select_tool(self, mock_llm: MagicMock) -> None:
        """测试工具选择"""
        agent = PlannerAgent(llm=mock_llm)
        step = ExecutionStep(
            step_id="step_1",
            description="读取文件",
        )
        selection = await agent.select_tool(step)
        assert selection.tool_name == "read_file"

    @pytest.mark.asyncio
    async def test_select_tool_predefined(self) -> None:
        """测试预定义工具选择"""
        agent = PlannerAgent()
        step = ExecutionStep(
            step_id="step_1",
            description="读取文件",
            tool_name="read_file",
            tool_args={"file_path": "test.csv"},
        )
        selection = await agent.select_tool(step, ["read_file", "write_file"])
        assert selection.tool_name == "read_file"
        assert selection.tool_args == {"file_path": "test.csv"}


class TestToolSelection:
    """测试工具选择模型"""

    def test_tool_selection_creation(self) -> None:
        """测试创建工具选择"""
        selection = ToolSelection(
            tool_name="read_file",
            tool_args={"file_path": "data.csv"},
            reasoning="需要读取数据文件",
        )
        assert selection.tool_name == "read_file"
        assert selection.tool_args == {"file_path": "data.csv"}
        assert selection.reasoning == "需要读取数据文件"


class TestReplanRequest:
    """测试重新规划请求模型"""

    def test_replan_request_creation(self) -> None:
        """测试创建重新规划请求"""
        original_plan = ExecutionPlan(
            steps=[ExecutionStep(step_id="step_1", description="步骤1")],
            reasoning="原始计划",
        )
        request = ReplanRequest(
            original_plan=original_plan,
            failed_steps=["step_1"],
            feedback="执行失败",
            context={"error": "文件不存在"},
        )
        assert request.original_plan == original_plan
        assert request.failed_steps == ["step_1"]
        assert request.feedback == "执行失败"
        assert request.context == {"error": "文件不存在"}
