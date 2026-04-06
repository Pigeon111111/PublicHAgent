"""Reflection Agent 单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.executor.schemas import ExecutionResult
from backend.agents.planner.schemas import ExecutionPlan, ExecutionStep
from backend.agents.reflection import ReflectionAgent, ReflectionResult
from backend.agents.reflection.schemas import (
    EvaluationCriteria,
    QualityLevel,
    StepEvaluation,
)


class TestReflectionResult:
    """测试反思结果模型"""

    def test_reflection_result_creation(self) -> None:
        """测试创建反思结果"""
        result = ReflectionResult(
            should_replan=True,
            feedback="执行不完整",
            quality_score=0.5,
            quality_level=QualityLevel.ACCEPTABLE,
            suggestions=["增加错误处理", "优化代码结构"],
            strengths=["代码简洁"],
            weaknesses=["缺少异常处理"],
        )
        assert result.should_replan is True
        assert result.feedback == "执行不完整"
        assert result.quality_score == 0.5
        assert result.quality_level == QualityLevel.ACCEPTABLE
        assert len(result.suggestions) == 2
        assert len(result.strengths) == 1
        assert len(result.weaknesses) == 1

    def test_reflection_result_defaults(self) -> None:
        """测试反思结果默认值"""
        result = ReflectionResult(
            should_replan=False,
            feedback="成功",
            quality_score=0.8,
        )
        assert result.quality_level == QualityLevel.ACCEPTABLE
        assert result.suggestions == []
        assert result.strengths == []
        assert result.weaknesses == []


class TestQualityLevel:
    """测试质量等级"""

    def test_quality_level_values(self) -> None:
        """测试质量等级值"""
        assert QualityLevel.EXCELLENT.value == "excellent"
        assert QualityLevel.GOOD.value == "good"
        assert QualityLevel.ACCEPTABLE.value == "acceptable"
        assert QualityLevel.POOR.value == "poor"
        assert QualityLevel.FAILED.value == "failed"


class TestEvaluationCriteria:
    """测试评估标准模型"""

    def test_evaluation_criteria_creation(self) -> None:
        """测试创建评估标准"""
        criteria = EvaluationCriteria(
            correctness=0.9,
            completeness=0.8,
            efficiency=0.7,
            clarity=0.85,
        )
        assert criteria.correctness == 0.9
        assert criteria.completeness == 0.8
        assert criteria.efficiency == 0.7
        assert criteria.clarity == 0.85

    def test_evaluation_criteria_defaults(self) -> None:
        """测试评估标准默认值"""
        criteria = EvaluationCriteria()
        assert criteria.correctness == 0.5
        assert criteria.completeness == 0.5


class TestStepEvaluation:
    """测试步骤评估模型"""

    def test_step_evaluation_creation(self) -> None:
        """测试创建步骤评估"""
        evaluation = StepEvaluation(
            step_id="step_1",
            success=True,
            output_quality=0.9,
            issues=[],
        )
        assert evaluation.step_id == "step_1"
        assert evaluation.success is True
        assert evaluation.output_quality == 0.9


class TestReflectionAgent:
    """测试 Reflection Agent"""

    def test_init_without_llm(self) -> None:
        """测试不带 LLM 初始化"""
        agent = ReflectionAgent()
        assert agent._llm is None
        assert agent._llm_client is None

    def test_init_with_llm(self) -> None:
        """测试带 LLM 初始化"""
        mock_llm = MagicMock()
        agent = ReflectionAgent(llm=mock_llm)
        assert agent._llm == mock_llm

    def test_get_quality_level(self) -> None:
        """测试获取质量等级"""
        agent = ReflectionAgent()
        assert agent._get_quality_level(0.95) == QualityLevel.EXCELLENT
        assert agent._get_quality_level(0.8) == QualityLevel.GOOD
        assert agent._get_quality_level(0.65) == QualityLevel.ACCEPTABLE
        assert agent._get_quality_level(0.45) == QualityLevel.POOR
        assert agent._get_quality_level(0.3) == QualityLevel.FAILED

    def test_should_replan_by_quality(self) -> None:
        """测试根据质量判断是否重新规划"""
        agent = ReflectionAgent()
        assert agent.should_replan(0.3, False, 0, 10) is True
        assert agent.should_replan(0.7, False, 0, 10) is False

    def test_should_replan_by_errors(self) -> None:
        """测试根据错误判断是否重新规划"""
        agent = ReflectionAgent()
        assert agent.should_replan(0.8, True, 0, 10) is True

    def test_should_replan_by_iterations(self) -> None:
        """测试根据迭代次数判断是否重新规划"""
        agent = ReflectionAgent()
        assert agent.should_replan(0.3, True, 10, 10) is False

    def test_generate_feedback_excellent(self) -> None:
        """测试生成优秀反馈"""
        agent = ReflectionAgent()
        results = [
            ExecutionResult(success=True, output="成功", error="", code="", execution_time=0.1),
        ]
        feedback = agent.generate_feedback(results, 0.95)
        assert "优秀" in feedback

    def test_generate_feedback_poor(self) -> None:
        """测试生成差评反馈"""
        agent = ReflectionAgent()
        results = [
            ExecutionResult(success=False, output="", error="错误", code="", execution_time=0.1),
        ]
        feedback = agent.generate_feedback(results, 0.3)
        assert "不理想" in feedback or "失败" in feedback

    def test_get_reflection_summary(self) -> None:
        """测试获取反思摘要"""
        agent = ReflectionAgent()
        result = ReflectionResult(
            should_replan=True,
            feedback="需要改进",
            quality_score=0.5,
            quality_level=QualityLevel.ACCEPTABLE,
            suggestions=["建议1"],
            strengths=["优点1"],
            weaknesses=["不足1"],
        )
        summary = agent.get_reflection_summary(result)
        assert "质量评分: 0.50" in summary
        assert "acceptable" in summary
        assert "需要改进" in summary


class TestReflectionAgentAsync:
    """测试 Reflection Agent 异步方法"""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """创建 Mock LLM"""
        mock = MagicMock()

        reflection_structured = AsyncMock()
        reflection_structured.ainvoke = AsyncMock(return_value=ReflectionResult(
            should_replan=False,
            feedback="执行成功",
            quality_score=0.85,
            quality_level=QualityLevel.GOOD,
            suggestions=["可以进一步优化"],
            strengths=["代码简洁", "执行高效"],
            weaknesses=["缺少注释"],
        ))

        step_structured = AsyncMock()
        step_structured.ainvoke = AsyncMock(return_value=StepEvaluation(
            step_id="step_1",
            success=True,
            output_quality=0.9,
            issues=[],
        ))

        criteria_structured = AsyncMock()
        criteria_structured.ainvoke = AsyncMock(return_value=EvaluationCriteria(
            correctness=0.9,
            completeness=0.85,
            efficiency=0.8,
            clarity=0.9,
        ))

        def mock_with_structured_output(model_class):
            if model_class == ReflectionResult:
                return reflection_structured
            elif model_class == StepEvaluation:
                return step_structured
            elif model_class == EvaluationCriteria:
                return criteria_structured
            return reflection_structured

        mock.with_structured_output = MagicMock(side_effect=mock_with_structured_output)
        return mock

    @pytest.mark.asyncio
    async def test_evaluate(self, mock_llm: MagicMock) -> None:
        """测试评估执行结果"""
        agent = ReflectionAgent(llm=mock_llm)
        plan = ExecutionPlan(
            steps=[ExecutionStep(step_id="step_1", description="步骤1")],
            reasoning="测试计划",
        )
        results = [
            ExecutionResult(success=True, output="成功", error="", code="", execution_time=0.1),
        ]
        result = await agent.evaluate(
            user_query="测试查询",
            plan=plan,
            execution_results=results,
        )
        assert result.quality_score == 0.85
        assert result.should_replan is False

    @pytest.mark.asyncio
    async def test_evaluate_step(self, mock_llm: MagicMock) -> None:
        """测试评估单个步骤"""
        agent = ReflectionAgent(llm=mock_llm)
        execution_result = ExecutionResult(
            success=True,
            output="步骤输出",
            error="",
            code="print('hello')",
            execution_time=0.1,
        )
        evaluation = await agent.evaluate_step(
            step_description="打印 hello",
            execution_result=execution_result,
        )
        assert evaluation.success is True
        assert evaluation.output_quality == 0.9

    @pytest.mark.asyncio
    async def test_evaluate_criteria(self, mock_llm: MagicMock) -> None:
        """测试按标准评估"""
        agent = ReflectionAgent(llm=mock_llm)
        results = [
            ExecutionResult(success=True, output="成功", error="", code="", execution_time=0.1),
        ]
        criteria = await agent.evaluate_criteria(
            user_query="测试查询",
            execution_results=results,
        )
        assert criteria.correctness == 0.9
        assert criteria.completeness == 0.85


class TestReflectionIntegration:
    """测试反思集成"""

    def test_quality_thresholds(self) -> None:
        """测试质量阈值"""
        assert ReflectionAgent.QUALITY_THRESHOLDS[QualityLevel.EXCELLENT] == 0.9
        assert ReflectionAgent.QUALITY_THRESHOLDS[QualityLevel.GOOD] == 0.75
        assert ReflectionAgent.QUALITY_THRESHOLDS[QualityLevel.ACCEPTABLE] == 0.6
        assert ReflectionAgent.QUALITY_THRESHOLDS[QualityLevel.POOR] == 0.4
        assert ReflectionAgent.QUALITY_THRESHOLDS[QualityLevel.FAILED] == 0.0

    def test_replan_threshold(self) -> None:
        """测试重新规划阈值"""
        assert ReflectionAgent.REPLAN_THRESHOLD == 0.5
