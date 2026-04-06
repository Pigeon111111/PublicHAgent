"""Reflection Agent 实现

提供执行结果评估、反馈生成、Replan 触发能力。
使用 with_structured_output 确保结构化输出。
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.base.llm_client import LLMClient
from backend.agents.executor.schemas import ExecutionResult
from backend.agents.planner.schemas import ExecutionPlan
from backend.agents.reflection.schemas import (
    EvaluationCriteria,
    QualityLevel,
    ReflectionResult,
    StepEvaluation,
)


class ReflectionAgent:
    """反思 Agent

    负责评估执行结果，生成反馈意见，
    决定是否需要 Replan，并提供质量评分。
    """

    QUALITY_THRESHOLDS = {
        QualityLevel.EXCELLENT: 0.9,
        QualityLevel.GOOD: 0.75,
        QualityLevel.ACCEPTABLE: 0.6,
        QualityLevel.POOR: 0.4,
        QualityLevel.FAILED: 0.0,
    }

    REPLAN_THRESHOLD = 0.5

    EVALUATION_PROMPT = """你是一个质量评估专家。请评估执行结果，判断是否成功解决了用户的问题。

评估要点：
1. 正确性：结果是否正确，是否符合预期
2. 完整性：是否完成了所有必要的步骤
3. 效率：执行是否高效，有无冗余操作
4. 清晰度：输出是否清晰易懂

请给出综合评估和改进建议。"""

    STEP_EVALUATION_PROMPT = """请评估以下执行步骤的结果：

步骤描述: {step_description}
执行输出: {output}
执行状态: {status}

请评估此步骤的执行质量。"""

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """初始化 Reflection Agent

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_default_llm()

    async def evaluate(
        self,
        user_query: str,
        plan: ExecutionPlan,
        execution_results: list[ExecutionResult],
        context: dict[str, Any] | None = None,
    ) -> ReflectionResult:
        """评估执行结果

        Args:
            user_query: 用户查询
            plan: 执行计划
            execution_results: 执行结果列表
            context: 额外上下文

        Returns:
            反思结果
        """
        llm = self._get_llm()

        execution_summary = self._format_execution_summary(execution_results)
        plan_summary = self._format_plan_summary(plan)

        context_str = ""
        if context:
            context_str = f"\n额外上下文:\n{self._format_context(context)}"

        user_message = f"""用户查询: {user_query}

执行计划:
{plan_summary}

执行结果:
{execution_summary}
{context_str}

请评估执行结果的质量，并给出改进建议。"""

        structured_llm = llm.with_structured_output(ReflectionResult)
        result = await structured_llm.ainvoke([
            SystemMessage(content=self.EVALUATION_PROMPT),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, ReflectionResult):
            result.quality_level = self._get_quality_level(result.quality_score)
            if result.quality_score < self.REPLAN_THRESHOLD and not result.should_replan:
                result.should_replan = True
            return result

        return ReflectionResult(
            should_replan=False,
            feedback="评估失败",
            quality_score=0.5,
            quality_level=QualityLevel.ACCEPTABLE,
            suggestions=["无法生成评估结果"],
        )

    async def evaluate_step(
        self,
        step_description: str,
        execution_result: ExecutionResult,
    ) -> StepEvaluation:
        """评估单个步骤

        Args:
            step_description: 步骤描述
            execution_result: 执行结果

        Returns:
            步骤评估
        """
        llm = self._get_llm()

        user_message = self.STEP_EVALUATION_PROMPT.format(
            step_description=step_description,
            output=execution_result.output[:500] if execution_result.output else "无输出",
            status="成功" if execution_result.success else f"失败: {execution_result.error}",
        )

        structured_llm = llm.with_structured_output(StepEvaluation)
        result = await structured_llm.ainvoke([
            SystemMessage(content="你是一个步骤评估专家。"),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, StepEvaluation):
            return result

        return StepEvaluation(
            step_id="unknown",
            success=execution_result.success,
            output_quality=0.5 if execution_result.success else 0.0,
            issues=[] if execution_result.success else [execution_result.error],
        )

    async def evaluate_criteria(
        self,
        user_query: str,
        execution_results: list[ExecutionResult],
    ) -> EvaluationCriteria:
        """按标准评估

        Args:
            user_query: 用户查询
            execution_results: 执行结果列表

        Returns:
            评估标准
        """
        llm = self._get_llm()

        execution_summary = self._format_execution_summary(execution_results)

        user_message = f"""用户查询: {user_query}

执行结果:
{execution_summary}

请按照正确性、完整性、效率、清晰度四个维度评估执行质量。"""

        structured_llm = llm.with_structured_output(EvaluationCriteria)
        result = await structured_llm.ainvoke([
            SystemMessage(content="你是一个质量评估专家。请按照多个维度评估执行质量。"),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, EvaluationCriteria):
            return result

        return EvaluationCriteria()

    def should_replan(
        self,
        quality_score: float,
        has_errors: bool,
        iteration_count: int,
        max_iterations: int,
    ) -> bool:
        """判断是否需要重新规划

        Args:
            quality_score: 质量评分
            has_errors: 是否有错误
            iteration_count: 当前迭代次数
            max_iterations: 最大迭代次数

        Returns:
            是否需要重新规划
        """
        if iteration_count >= max_iterations:
            return False

        if has_errors:
            return True

        return quality_score < self.REPLAN_THRESHOLD

    def generate_feedback(
        self,
        results: list[ExecutionResult],
        quality_score: float,
    ) -> str:
        """生成反馈意见

        Args:
            results: 执行结果列表
            quality_score: 质量评分

        Returns:
            反馈意见
        """
        failed_steps = [r for r in results if not r.success]
        success_steps = [r for r in results if r.success]

        feedback_parts = []

        if quality_score >= 0.9:
            feedback_parts.append("执行结果优秀，完全满足用户需求。")
        elif quality_score >= 0.75:
            feedback_parts.append("执行结果良好，基本满足用户需求。")
        elif quality_score >= 0.6:
            feedback_parts.append("执行结果可接受，但仍有改进空间。")
        else:
            feedback_parts.append("执行结果不理想，需要改进。")

        if failed_steps:
            feedback_parts.append(f"有 {len(failed_steps)} 个步骤执行失败。")
            for step in failed_steps[:3]:
                feedback_parts.append(f"  - 错误: {step.error[:100]}")

        if success_steps:
            feedback_parts.append(f"成功执行 {len(success_steps)} 个步骤。")

        return "\n".join(feedback_parts)

    def _get_quality_level(self, score: float) -> QualityLevel:
        """根据评分获取质量等级

        Args:
            score: 质量评分

        Returns:
            质量等级
        """
        for level, threshold in self.QUALITY_THRESHOLDS.items():
            if score >= threshold:
                return level
        return QualityLevel.FAILED

    def _format_execution_summary(self, results: list[ExecutionResult]) -> str:
        """格式化执行摘要"""
        if not results:
            return "无执行结果"

        lines = []
        for i, result in enumerate(results):
            status = "✓" if result.success else "✗"
            output_preview = result.output[:100] if result.output else "无输出"
            lines.append(f"  {i + 1}. [{status}] {output_preview}")
            if result.error:
                lines.append(f"     错误: {result.error[:100]}")

        return "\n".join(lines)

    def _format_plan_summary(self, plan: ExecutionPlan) -> str:
        """格式化计划摘要"""
        if not plan.steps:
            return "空计划"

        lines = []
        for step in plan.steps:
            lines.append(f"  - [{step.step_id}] {step.description}")

        return "\n".join(lines)

    def _format_context(self, context: dict[str, Any]) -> str:
        """格式化上下文信息"""
        lines = []
        for key, value in context.items():
            if isinstance(value, str):
                lines.append(f"- {key}: {value}")
            elif isinstance(value, dict):
                lines.append(f"- {key}: {self._format_context(value)}")
            elif isinstance(value, list):
                lines.append(f"- {key}: {', '.join(str(v) for v in value)}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def get_reflection_summary(self, result: ReflectionResult) -> str:
        """获取反思摘要

        Args:
            result: 反思结果

        Returns:
            反思摘要字符串
        """
        suggestions_str = "\n".join(f"  - {s}" for s in result.suggestions) if result.suggestions else "  无"
        strengths_str = "\n".join(f"  - {s}" for s in result.strengths) if result.strengths else "  无"
        weaknesses_str = "\n".join(f"  - {w}" for w in result.weaknesses) if result.weaknesses else "  无"

        return f"""反思摘要:
质量评分: {result.quality_score:.2f} ({result.quality_level.value})
是否需要重新规划: {'是' if result.should_replan else '否'}

反馈意见:
{result.feedback}

改进建议:
{suggestions_str}

优点:
{strengths_str}

不足:
{weaknesses_str}"""
