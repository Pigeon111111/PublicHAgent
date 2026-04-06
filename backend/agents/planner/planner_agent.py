"""Planner Agent 实现

提供计划生成、工具选择、Replan 能力。
使用 with_structured_output 确保结构化输出。
集成 MemoryManager 实现记忆注入。
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.base.llm_client import LLMClient
from backend.agents.memory.manager import MemoryManager
from backend.agents.planner.schemas import (
    ExecutionPlan,
    ExecutionStep,
    ReplanRequest,
    ToolSelection,
)
from backend.tools.registry import get_tool_registry


class PlannerAgent:
    """计划生成 Agent

    负责将用户请求分解为可执行的步骤序列，
    根据步骤选择合适的工具，并支持 Replan 能力。
    """

    SYSTEM_PROMPT = """你是一个公共卫生数据分析专家和计划制定者。你的任务是将用户的请求分解为可执行的步骤序列。

在制定计划时，请遵循以下原则：
1. 步骤应该具体、可执行
2. 每个步骤应该有明确的输入和输出
3. 步骤之间应该有合理的依赖关系
4. 选择合适的工具来执行每个步骤

可用的工具类型：
- read_file: 读取文件内容
- write_file: 写入文件内容
- edit_file: 编辑文件（搜索替换）
- python_code: 执行 Python 代码进行数据分析
- statistical_test: 执行统计检验
- visualization: 生成数据可视化

请确保计划合理、可执行，并能够解决用户的问题。"""

    REPLAN_PROMPT = """根据执行反馈，需要重新制定计划。

原始计划执行情况：
- 失败的步骤: {failed_steps}
- 反馈信息: {feedback}

请分析失败原因，并制定新的执行计划。可以：
1. 修改失败步骤的参数
2. 添加新的准备步骤
3. 选择不同的工具
4. 调整执行顺序"""

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        memory_manager: MemoryManager | None = None,
        token_budget: int = 500,
    ) -> None:
        """初始化 Planner Agent

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
            memory_manager: 记忆管理器实例
            token_budget: 记忆摘要 Token 预算
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._memory_manager = memory_manager
        self._token_budget = token_budget

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_default_llm()

    def _get_available_tools(self) -> list[str]:
        """获取可用工具列表"""
        try:
            registry = get_tool_registry()
            return registry.list_tools()
        except Exception:
            return ["read_file", "write_file", "edit_file", "python_code"]

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
        llm = self._get_llm()
        available_tools = self._get_available_tools()

        context_str = ""
        if context:
            context_str = f"\n额外上下文:\n{self._format_context(context)}"

        memory_context = ""
        if self._memory_manager and user_id:
            memory_context = self._load_memory_context(user_id, user_query)

        user_message = f"""用户查询: {user_query}
识别意图: {intent}
可用工具: {', '.join(available_tools)}
{context_str}
{memory_context}

请制定详细的执行计划。"""

        structured_llm = llm.with_structured_output(ExecutionPlan)
        result = await structured_llm.ainvoke([
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, ExecutionPlan):
            return result

        return ExecutionPlan(
            steps=[],
            reasoning="计划生成失败，返回空计划",
            estimated_complexity="unknown",
        )

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

        structured_llm = llm.with_structured_output(ExecutionPlan)
        result = await structured_llm.ainvoke([
            SystemMessage(content=self.REPLAN_PROMPT),
            HumanMessage(content=user_message),
        ])

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

        structured_llm = llm.with_structured_output(ToolSelection)
        result = await structured_llm.ainvoke([
            SystemMessage(content="你是一个工具选择专家。请根据步骤描述选择最合适的工具。"),
            HumanMessage(content=prompt),
        ])

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
