"""Planner Agent 实现

提供计划生成、工具选择、Replan 能力。
使用 with_structured_output 确保结构化输出。
集成 MemoryManager 实现记忆注入。
支持能力缺口识别和 Skill 创建/更新建议。
"""

import asyncio
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.base.llm_client import LLMClient, invoke_structured_output
from backend.agents.memory.manager import MemoryManager
from backend.agents.planner.schemas import (
    ExecutionPlan,
    ExecutionStep,
    ReplanRequest,
    ToolSelection,
)
from backend.learning.skill_learning import SkillLearningService
from backend.tools.registry import get_tool_registry
from backend.tools.skills.loader import SkillLoader


class PlannerAgent:
    """计划生成 Agent

    负责将用户请求分解为可执行的步骤序列，
    根据步骤选择合适的工具，并支持 Replan 能力。
    支持能力缺口识别和 Skill 创建/更新建议。
    """

    SYSTEM_PROMPT = """你是一个公共卫生数据分析专家和计划制定者。你的任务是将用户的请求分解为可执行的步骤序列。

在制定计划时，请遵循以下原则：
1. 步骤应该具体、可执行
2. 每个步骤应该有明确的输入和输出
3. 步骤之间应该有合理的依赖关系
4. 选择合适的工具来执行每个步骤

## 工具能力描述

在为步骤选择工具时，请仔细阅读工具的能力描述，确保选择的工具能够完成任务。

## 能力缺口识别

当你发现现有工具无法完成用户任务时：

1. **识别能力缺口**：
   - 分析任务需求
   - 检查现有工具的能力范围
   - 确定缺失的能力

2. **判断是否有类似 Skill 可以扩展**：
   - 如果有类似的 Skill，建议更新该 Skill，添加新功能
   - 如果没有类似的 Skill，建议创建新 Skill

3. **提供 Skill 建议**：
   - 明确说明需要创建还是更新 Skill
   - 提供能力描述
   - 建议参数定义

## Skill 创建/更新示例

示例 1：用户需要做"倾向性评分匹配分析"，但现有工具不支持
- 能力缺口：缺少倾向性评分匹配分析能力
- 相关 Skill：regression_analysis（回归分析）
- 建议：更新 regression_analysis Skill，添加 PSM 分析功能

示例 2：用户需要做"Meta 分析"，但现有工具不支持
- 能力缺口：缺少 Meta 分析能力
- 相关 Skill：无
- 建议：创建新的 meta_analysis Skill

请确保计划合理、可执行，并能够解决用户的问题。如果发现能力缺口，请在计划中明确指出。"""

    CAPABILITY_CHECK_PROMPT = """
## 可用工具能力

{tools_capability}

## 可用 Skills

{skills_capability}

请根据以上工具能力信息，制定执行计划。如果发现能力缺口，请提供 Skill 创建/更新建议。
"""

    REPLAN_PROMPT = """根据执行反馈，需要重新制定计划。

原始计划执行情况：
- 失败的步骤: {failed_steps}
- 反馈信息: {feedback}

请分析失败原因，并制定新的执行计划。可以：
1. 修改失败步骤的参数
2. 添加新的准备步骤
3. 选择不同的工具
4. 调整执行顺序

如果发现能力缺口，请提供 Skill 创建/更新建议。"""

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        memory_manager: MemoryManager | None = None,
        token_budget: int = 500,
        user_id: str = "default",
    ) -> None:
        """初始化 Planner Agent

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
            memory_manager: 记忆管理器实例
            token_budget: 记忆摘要 Token 预算
            user_id: 用户 ID，用于获取用户配置的模型
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._memory_manager = memory_manager
        self._token_budget = token_budget
        self._skill_loader = SkillLoader()
        self._skill_learning = SkillLearningService()
        self._user_id = user_id

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_planner_llm(self._user_id)

    def _get_available_tools(self) -> list[str]:
        """获取可用工具列表"""
        try:
            registry = get_tool_registry()
            return registry.list_tools()
        except Exception:
            return ["read_file", "write_file", "edit_file", "python_code"]

    def _get_tools_capability_description(self) -> str:
        """获取工具能力描述"""
        try:
            registry = get_tool_registry()
            return registry.get_capabilities_description()
        except Exception:
            return "工具能力描述获取失败"

    def _get_skills_capability_description(self) -> str:
        """获取 Skills 能力描述"""
        try:
            skills = self._skill_loader.load_all_skills()
            if not skills:
                return "暂无可用 Skills"

            lines = []
            for skill in skills:
                lines.append(f"### {skill.name}")
                lines.append(f"描述: {skill.description}")
                if skill.capability.capability:
                    lines.append(f"能力: {skill.capability.capability}")
                if skill.capability.limitations:
                    lines.append("限制:")
                    for limit in skill.capability.limitations:
                        lines.append(f"  - {limit}")
                if skill.capability.applicable_scenarios:
                    lines.append("适用场景:")
                    for scenario in skill.capability.applicable_scenarios:
                        lines.append(f"  - {scenario}")
                lines.append("")

            return "\n".join(lines)
        except Exception:
            return "Skills 能力描述获取失败"

    async def create_plan(
        self,
        user_query: str,
        intent: str,
        context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> ExecutionPlan:
        """创建执行计划

        Args:
            user_query: 用户查询
            intent: 识别的意图
            context: 额外上下文信息
            user_id: 用户 ID（用于记忆注入）

        Returns:
            执行计划
        """
        available_tools = self._get_available_tools()

        context_str = ""
        if context:
            context_str = f"\n额外上下文:\n{self._format_context(context)}"

        memory_context = ""
        if self._memory_manager and user_id:
            memory_context = self._load_memory_context(user_id, user_query)

        # 获取工具和 Skills 能力描述
        tools_capability = self._get_tools_capability_description()
        skills_capability = self._get_skills_capability_description()

        capability_info = self.CAPABILITY_CHECK_PROMPT.format(
            tools_capability=tools_capability,
            skills_capability=skills_capability,
        )

        user_message = f"""用户查询: {user_query}
识别意图: {intent}
可用工具: {', '.join(available_tools)}
{context_str}
{memory_context}

{capability_info}

请制定详细的执行计划。如果发现现有工具无法完成任务，请识别能力缺口并提供 Skill 创建/更新建议。"""

        try:
            llm = self._get_llm()
            result = await asyncio.wait_for(
                invoke_structured_output(
                    llm,
                    [
                        SystemMessage(content=self.SYSTEM_PROMPT),
                        HumanMessage(content=user_message),
                    ],
                    ExecutionPlan,
                ),
                timeout=20,
            )

            if isinstance(result, ExecutionPlan):
                return result
        except Exception:
            pass

        return self._create_fallback_plan(user_query)

    async def replan(
        self,
        request: ReplanRequest,
    ) -> ExecutionPlan:
        """根据执行反馈重新制定计划

        Args:
            request: 重新规划请求

        Returns:
            新的执行计划
        """
        llm = self._get_llm()
        available_tools = self._get_available_tools()

        original_steps = "\n".join([
            f"- {step.step_id}: {step.description}"
            for step in request.original_plan.steps
        ])

        user_message = f"""原始计划:
{original_steps}

失败的步骤: {', '.join(request.failed_steps)}
反馈信息: {request.feedback}
可用工具: {', '.join(available_tools)}

请制定新的执行计划。"""

        result = await invoke_structured_output(
            llm,
            [
                SystemMessage(content=self.REPLAN_PROMPT),
                HumanMessage(content=user_message),
            ],
            ExecutionPlan,
        )

        if isinstance(result, ExecutionPlan):
            return result

        return request.original_plan

    async def select_tool(
        self,
        step: ExecutionStep,
        available_tools: list[str] | None = None,
    ) -> ToolSelection:
        """为步骤选择合适的工具

        Args:
            step: 执行步骤
            available_tools: 可用工具列表

        Returns:
            工具选择结果
        """
        if available_tools is None:
            available_tools = self._get_available_tools()

        if step.tool_name and step.tool_name in available_tools:
            return ToolSelection(
                tool_name=step.tool_name,
                tool_args=step.tool_args,
                reasoning=f"使用步骤预定义的工具: {step.tool_name}",
            )

        llm = self._get_llm()

        prompt = f"""步骤描述: {step.description}
预期输出: {step.expected_output}
可用工具: {', '.join(available_tools)}

请选择最合适的工具来执行此步骤。"""

        result = await invoke_structured_output(
            llm,
            [
                SystemMessage(content="你是一个工具选择专家。请根据步骤描述选择最合适的工具。"),
                HumanMessage(content=prompt),
            ],
            ToolSelection,
        )

        if isinstance(result, ToolSelection):
            return result

        return ToolSelection(
            tool_name="python_code",
            tool_args={},
            reasoning="默认使用 Python 代码执行",
        )

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

    def _load_memory_context(self, user_id: str, query: str) -> str:
        """加载记忆上下文

        Args:
            user_id: 用户 ID
            query: 当前查询

        Returns:
            记忆上下文字符串
        """
        if not self._memory_manager:
            return ""

        try:
            memory_summary = self._memory_manager.get_relevant_memories_for_planning(
                user_id=user_id,
                query=query,
                token_budget=self._token_budget,
            )
            if memory_summary and memory_summary != "暂无相关历史记忆":
                return f"\n历史记忆参考:\n{memory_summary}"
        except Exception:
            pass

        return ""

    def validate_plan(self, plan: ExecutionPlan) -> tuple[bool, list[str]]:
        """验证计划的有效性

        Args:
            plan: 执行计划

        Returns:
            (是否有效, 错误信息列表)
        """
        errors: list[str] = []

        if not plan.steps:
            errors.append("计划没有步骤")
            return False, errors

        step_ids = {step.step_id for step in plan.steps}

        for step in plan.steps:
            if not step.step_id:
                errors.append(f"步骤缺少 step_id: {step.description}")

            if not step.description:
                errors.append(f"步骤缺少描述: {step.step_id}")

            for dep in step.dependencies:
                if dep not in step_ids:
                    errors.append(f"步骤 {step.step_id} 依赖不存在的步骤: {dep}")

        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            step = next((s for s in plan.steps if s.step_id == step_id), None)
            if step:
                for dep in step.dependencies:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(step_id)
            return False

        for step in plan.steps:
            if step.step_id not in visited and has_cycle(step.step_id):
                errors.append("计划存在循环依赖")
                break

        return len(errors) == 0, errors

    def get_next_step(
        self,
        plan: ExecutionPlan,
        completed_steps: set[str],
    ) -> ExecutionStep | None:
        """获取下一个可执行的步骤

        Args:
            plan: 执行计划
            completed_steps: 已完成的步骤 ID 集合

        Returns:
            下一个可执行的步骤，如果没有则返回 None
        """
        for step in plan.steps:
            if step.step_id in completed_steps:
                continue

            all_deps_completed = all(
                dep in completed_steps for dep in step.dependencies
            )

            if all_deps_completed:
                return step

        return None

    def get_plan_summary(self, plan: ExecutionPlan) -> str:
        """获取计划摘要

        Args:
            plan: 执行计划

        Returns:
            计划摘要字符串
        """
        if not plan.steps:
            return "空计划"

        steps_str = "\n".join([
            f"  {i + 1}. [{step.step_id}] {step.description}"
            for i, step in enumerate(plan.steps)
        ])

        return f"""计划摘要:
步骤数: {len(plan.steps)}
复杂度: {plan.estimated_complexity}
推理: {plan.reasoning}

步骤列表:
{steps_str}"""

    def _create_fallback_plan(self, user_query: str) -> ExecutionPlan:
        """在 LLM 不可用时创建可执行的回退计划。"""
        reusable_skill = self._skill_learning.find_reusable_skill(user_query)
        description = "复用已学习 Skill 执行数据分析" if reusable_skill else "执行通用数据分析并沉淀成功路径"
        expected = "在会话输出目录生成 analysis_report.md 和 analysis_result.json"

        tool_args: dict[str, Any] = {
            "analysis_method": user_query,
            "analysis_type": "auto",
            "prefer_fallback": True,
        }
        if reusable_skill:
            tool_args["skill_name"] = reusable_skill

        return ExecutionPlan(
            steps=[
                ExecutionStep(
                    step_id="step_1",
                    description=description,
                    tool_name="python_code",
                    tool_args=tool_args,
                    expected_output=expected,
                )
            ],
            reasoning=(
                f"LLM 计划不可用，使用已学习 Skill: {reusable_skill}"
                if reusable_skill
                else "LLM 计划不可用，使用通用数据分析回退流程。"
            ),
            estimated_complexity="medium",
        )
