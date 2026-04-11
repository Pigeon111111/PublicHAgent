"""Planner 分层 Skill 披露测试。"""

from unittest.mock import MagicMock, patch

from backend.agents.planner import ExecutionPlan, ExecutionStep, PlannerAgent


def test_attach_variant_hints_to_plan() -> None:
    """当检索到可复用变体时，应自动补充 skill_name 与 method_variant。"""
    agent = PlannerAgent()
    agent._skill_learning = MagicMock()
    agent._skill_learning.find_reusable_skill.return_value = "learned_variant"
    agent._get_preferred_variants = MagicMock(return_value={"regression_analysis": "logistic_regression"})

    mock_skill = MagicMock()
    mock_skill.metadata.method_variant = "logistic_regression"
    mock_skill.name = "learned_variant"

    with patch("backend.agents.planner.planner_agent.get_skill_registry") as mock_registry_factory:
        mock_registry_factory.return_value.get.return_value = mock_skill
        plan = ExecutionPlan(
            steps=[
                ExecutionStep(
                    step_id="step_1",
                    description="执行回归分析",
                    tool_name="python_code",
                    tool_args={},
                )
            ],
            reasoning="测试",
        )
        enriched = agent._attach_variant_hints(
            plan,
            user_query="做 logistic 回归",
            intent="regression_analysis",
            user_id="default",
        )

    assert enriched.steps[0].tool_args["skill_name"] == "learned_variant"
    assert enriched.steps[0].tool_args["method_variant"] == "logistic_regression"
    assert enriched.steps[0].tool_args["analysis_type"] == "regression_analysis"
