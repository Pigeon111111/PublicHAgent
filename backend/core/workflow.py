"""LangGraph 工作流模块

使用 LangGraph 构建多智能体工作流，实现计划-执行-反思循环。
"""

from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import StateSnapshot
from pydantic import BaseModel, Field

from backend.agents.base.llm_client import LLMClient
from backend.agents.executor.context import IsolatedExecutionContext
from backend.agents.executor.executor_agent import ExecutorAgent
from backend.agents.intent.recognizer import IntentRecognizer
from backend.agents.memory.factory import get_optional_memory_manager
from backend.agents.memory.manager import MemoryManager
from backend.agents.planner.planner_agent import PlannerAgent
from backend.agents.planner.schemas import (
    ExecutionPlan as PlannerExecutionPlan,
)
from backend.agents.planner.schemas import (
    ExecutionStep as PlannerExecutionStep,
)
from backend.core.checkpoint_store import get_workflow_checkpoint_manager
from backend.core.session_workspace import SessionWorkspaceManager
from backend.core.state import (
    AgentState,
    create_execution_step,
    create_initial_state,
    create_plan,
)
from backend.core.state import (
    ExecutionStep as StateExecutionStep,
)
from backend.evaluation.orchestrator import EvaluationOrchestrator
from backend.evaluation.schemas import EvaluationReport
from backend.learning.skill_learning import SkillLearningService
from backend.learning.trajectory import (
    AnalysisTrajectory,
    AttemptRecord,
    TrajectoryRecorder,
    ValidationRecord,
)
from backend.sandbox.safe_executor import SafeCodeExecutor, SafeExecutionContext
from backend.tools.registry import get_tool_registry


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
        user_id: str = "default",
        cancellation_checker: Callable[[], bool] | None = None,
    ) -> None:
        """初始化工作流

        Args:
            llm: LLM 实例
            intent_recognizer: 意图识别器实例
            user_id: 用户 ID，用于获取用户配置的模型
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._intent_recognizer = intent_recognizer
        self._workflow: StateGraph | None = None
        self._compiled_workflow: Any = None
        self._checkpointer: Any | None = None
        self._compiled_checkpointer_id: int | None = None
        self._user_id = user_id
        self._memory_manager: MemoryManager | None = get_optional_memory_manager(user_id)
        self._workspace_manager = SessionWorkspaceManager()
        self._trajectory_recorder = TrajectoryRecorder()
        self._skill_learning = SkillLearningService()
        self._evaluator = EvaluationOrchestrator()
        self._cancellation_checker = cancellation_checker
        self._durability_mode: Literal["sync", "async", "exit"] = "sync"

    def set_cancellation_checker(self, cancellation_checker: Callable[[], bool] | None) -> None:
        """设置外部中断检查器。"""
        self._cancellation_checker = cancellation_checker

    def _is_cancelled(self) -> bool:
        """检查当前工作流是否已被用户中断。"""
        return bool(self._cancellation_checker and self._cancellation_checker())

    def _cancelled_update(self) -> dict[str, Any]:
        """返回统一的中断状态更新。"""
        return {
            "final_result": "执行已被用户中断",
            "messages": [AIMessage(content="执行已被用户中断")],
        }

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_planner_llm(self._user_id)

    def _get_intent_recognizer(self) -> IntentRecognizer:
        """获取意图识别器实例"""
        if self._intent_recognizer is None:
            try:
                llm = self._get_llm()
            except Exception:
                llm = None
            self._intent_recognizer = IntentRecognizer(llm)
        return self._intent_recognizer

    async def _intent_node(self, state: AgentState) -> dict[str, Any]:
        """意图识别节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        if self._is_cancelled():
            return self._cancelled_update()

        recognizer = self._get_intent_recognizer()
        result = await recognizer.recognize(state["user_query"])
        if result.intent == "general_query" and state.get("workspace", {}).get("input_files"):
            result.intent = "data_analysis"
            result.confidence = max(result.confidence, 0.65)

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
        if self._is_cancelled():
            return self._cancelled_update()

        with suppress(Exception):
            await get_tool_registry().refresh_mcp_tools()

        planner = PlannerAgent(
            llm=self._llm,
            memory_manager=self._memory_manager,
            user_id=self._user_id,
        )
        plan_model = await planner.create_plan(
            user_query=state["user_query"],
            intent=state["intent"],
            context={
                "workspace": state.get("workspace", {}),
                "user_context": state.get("user_context", {}),
            },
            user_id=self._user_id,
        )

        steps = [self._planner_step_to_state_step(step) for step in plan_model.steps]

        plan = create_plan(steps)

        return {
            "plan": plan,
            "plan_model": plan_model,
            "should_replan": False,
            "messages": [
                AIMessage(content=f"已制定计划，共 {len(steps)} 个步骤:\n{plan_model.reasoning}")
            ],
        }

    async def _executor_node(self, state: AgentState) -> dict[str, Any]:
        """执行节点

        Args:
            state: 当前状态

        Returns:
            状态更新字典
        """
        if self._is_cancelled():
            return self._cancelled_update()

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

        current_step = cast(StateExecutionStep, dict(plan["steps"][current_index]))
        current_step["status"] = "running"

        with suppress(Exception):
            await get_tool_registry().refresh_mcp_tools()

        workspace = state.get("workspace") or self._prepare_workspace(
            state["session_id"],
            state["user_query"],
            state.get("user_context", {}),
        )
        safe_executor = self._create_safe_executor(workspace)
        executor = ExecutorAgent(llm=self._llm, user_id=self._user_id, safe_executor=safe_executor)

        plan_model = state.get("plan_model")
        planner_step = self._get_planner_step(plan_model, current_step, current_index)
        context = self._build_isolated_context(
            plan_model=plan_model,
            current_step=planner_step,
            current_index=current_index,
            state=state,
            workspace=workspace,
        )

        result = await executor.execute_step(planner_step, context)
        if self._is_cancelled():
            return self._cancelled_update()
        current_step["result"] = result.output
        current_step["error"] = result.error or None
        current_step["status"] = "completed" if result.success else "failed"

        new_results = state["execution_results"] + [current_step]
        new_plan = {
            **plan,
            "current_step_index": current_index + 1,
        }

        return {
            "plan": new_plan,
            "current_step": current_step,
            "execution_results": new_results,
            "executor_results": state.get("executor_results", []) + [result],
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
        if self._is_cancelled():
            return self._cancelled_update()

        evaluation = self._evaluate_execution(state)
        executor_results = state.get("executor_results", [])
        validation = (
            self._validation_from_evaluation(evaluation)
            if evaluation is not None
            else self._validate_execution(executor_results)
        )
        trajectory = self._build_trajectory(state, validation, evaluation)
        learned_skill = None
        try:
            learned_skill = self._skill_learning.learn_from_trajectory(trajectory)
        except Exception as exc:
            validation.issues.append(f"Skill 学习失败: {exc}")
        if learned_skill:
            trajectory.learned_skill = learned_skill
        selected_skill = self._select_associated_skill(state)
        trajectory_path = self._trajectory_recorder.save(trajectory)

        final_result = self._build_final_result(
            state,
            validation,
            evaluation,
            learned_skill,
            str(trajectory_path),
        )
        self._write_memory_records(
            state=state,
            validation=validation,
            evaluation=evaluation,
            final_result=final_result,
            learned_skill=learned_skill,
            trajectory=trajectory,
        )
        should_replan = not validation.passed and state["iteration_count"] < state["max_iterations"]
        feedback = "执行成功" if validation.passed else "; ".join(validation.issues)

        return {
            "reflection_feedback": feedback,
            "should_replan": should_replan,
            "final_result": final_result,
            "trajectory_id": trajectory.trajectory_id,
            "learned_skill": learned_skill,
            "selected_skill": selected_skill,
            "task_family": evaluation.task_family if evaluation is not None else state.get("intent", ""),
            "evaluation_report": evaluation.model_dump() if evaluation is not None else {},
            "evaluation_score": evaluation.final_score if evaluation is not None else 0.0,
            "messages": [
                AIMessage(content=f"反思结果: {'成功' if validation.passed else '需要改进'}\n反馈: {feedback}")
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

        if self._is_cancelled():
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

    def _prepare_workspace(
        self,
        session_id: str,
        user_query: str,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """准备本次分析的隔离工作区。"""
        workspace = self._workspace_manager.prepare(
            session_id=session_id,
            user_query=user_query,
            user_context=user_context or {},
        )
        return workspace.to_context()

    def _create_safe_executor(self, workspace: dict[str, Any]) -> SafeCodeExecutor:
        """基于工作区创建受限代码执行器。"""
        context = SafeExecutionContext(
            session_id=str(workspace.get("session_id") or "default"),
            input_dir=Path(str(workspace["input_dir"])),
            workspace_dir=Path(str(workspace["workspace_dir"])),
            output_dir=Path(str(workspace["output_dir"])),
            input_files=[Path(str(path)) for path in workspace.get("input_files", [])],
        )
        return SafeCodeExecutor(context, should_cancel=self._is_cancelled)

    def _planner_step_to_state_step(self, step: PlannerExecutionStep) -> StateExecutionStep:
        """把 Planner 步骤转换为 LangGraph 状态步骤。"""
        return create_execution_step(
            step_id=step.step_id,
            action=step.description,
            tool_name=step.tool_name or "python_code",
            tool_args=step.tool_args,
            status="pending",
        )

    def _get_planner_step(
        self,
        plan_model: Any,
        current_step: Any,
        current_index: int,
    ) -> PlannerExecutionStep:
        """获取当前步骤的 Planner 模型，兼容旧状态结构。"""
        if isinstance(plan_model, PlannerExecutionPlan) and current_index < len(plan_model.steps):
            return plan_model.steps[current_index]

        return PlannerExecutionStep(
            step_id=str(current_step.get("step_id") or f"step_{current_index + 1}"),
            description=str(current_step.get("action") or ""),
            tool_name=str(current_step.get("tool_name") or "python_code"),
            tool_args=dict(current_step.get("tool_args") or {}),
            expected_output="生成 analysis_report.md 和 analysis_result.json",
        )

    def _build_isolated_context(
        self,
        plan_model: Any,
        current_step: PlannerExecutionStep,
        current_index: int,
        state: AgentState,
        workspace: dict[str, Any],
    ) -> IsolatedExecutionContext:
        """构建 Executor 可见的最小上下文。"""
        _ = workspace
        previous_result = ""
        if state.get("execution_results"):
            previous_result = str(state["execution_results"][-1].get("result") or "")

        try:
            available_tools = get_tool_registry().list_tools()
        except Exception:
            available_tools = ["python_code"]

        total_steps = 1
        if isinstance(plan_model, PlannerExecutionPlan):
            total_steps = max(len(plan_model.steps), 1)
        else:
            state_plan = state.get("plan")
            if state_plan is not None:
                total_steps = int(state_plan["total_steps"])

        return IsolatedExecutionContext(
            current_step=current_step,
            previous_result=previous_result,
            required_output=current_step.expected_output or "生成可复用的数据分析结果",
            available_tools=available_tools,
            step_index=current_index,
            total_steps=total_steps,
        )

    def _validate_execution(self, executor_results: list[Any]) -> ValidationRecord:
        """验证执行是否真的产出数据分析结果。"""
        checks: list[str] = []
        issues: list[str] = []
        output_files: list[str] = []

        if not executor_results:
            return ValidationRecord(passed=False, issues=["没有执行结果"])

        for index, result in enumerate(executor_results, start=1):
            if not getattr(result, "success", False):
                issues.append(f"第 {index} 步执行失败: {getattr(result, 'error', '')}")
            artifacts = getattr(result, "artifacts", {}) or {}
            output_files.extend(str(path) for path in artifacts.get("output_files", []))

        report_paths = [path for path in output_files if Path(path).name == "analysis_report.md"]
        json_paths = [path for path in output_files if Path(path).name == "analysis_result.json"]

        if report_paths:
            checks.append("已生成 analysis_report.md")
        else:
            issues.append("缺少 analysis_report.md")

        if json_paths:
            checks.append("已生成 analysis_result.json")
        else:
            issues.append("缺少 analysis_result.json")

        for file_path in report_paths + json_paths:
            path = Path(file_path)
            if not path.exists() or path.stat().st_size == 0:
                issues.append(f"输出文件为空或不存在: {path.name}")

        passed = not issues and all(getattr(result, "success", False) for result in executor_results)
        return ValidationRecord(passed=passed, checks=checks, issues=issues)

    def _evaluate_execution(self, state: AgentState) -> EvaluationReport | None:
        """优先执行结构化评估，异常时回退旧验证链路。"""
        try:
            return self._evaluator.evaluate(
                intent=state.get("intent", ""),
                executor_results=state.get("executor_results", []),
                workspace=state.get("workspace", {}),
            )
        except Exception:
            return None

    def _validation_from_evaluation(self, evaluation: EvaluationReport) -> ValidationRecord:
        """把结构化评估折叠成兼容旧逻辑的验证结果。"""
        checks = []
        if evaluation.passed:
            checks.append(f"结构化评估通过，得分 {evaluation.final_score:.2f}")
        checks.extend(
            finding.message
            for finding in evaluation.findings
            if finding.severity == "info"
        )
        issues = list(evaluation.hard_failures)
        if not issues and not evaluation.passed:
            issues.append(evaluation.summary)
        return ValidationRecord(
            passed=evaluation.passed,
            checks=checks,
            issues=issues,
        )

    def _build_trajectory(
        self,
        state: AgentState,
        validation: ValidationRecord,
        evaluation: EvaluationReport | None,
    ) -> AnalysisTrajectory:
        """把一次分析任务保存为可学习轨迹。"""
        attempts: list[AttemptRecord] = []
        executor_results = state.get("executor_results", [])
        execution_steps = state.get("execution_results", [])

        for index, step in enumerate(execution_steps):
            result = executor_results[index] if index < len(executor_results) else None
            attempts.append(
                AttemptRecord(
                    step_id=str(step.get("step_id") or f"step_{index + 1}"),
                    description=str(step.get("action") or ""),
                    success=bool(getattr(result, "success", step.get("status") == "completed")),
                    code=str(getattr(result, "code", "")),
                    output=str(getattr(result, "output", step.get("result") or "")),
                    error=str(getattr(result, "error", step.get("error") or "")),
                    artifacts=dict(getattr(result, "artifacts", {}) or {}),
                )
            )

        plan_model = state.get("plan_model")
        plan_summary = getattr(plan_model, "reasoning", "") if plan_model is not None else ""
        workspace = state.get("workspace", {})

        return AnalysisTrajectory(
            user_id=self._user_id,
            session_id=state.get("session_id", "default"),
            user_query=state["user_query"],
            intent=state.get("intent", ""),
            task_family=evaluation.task_family if evaluation is not None else state.get("intent", ""),
            data_files=[str(path) for path in workspace.get("input_files", [])],
            plan_summary=plan_summary,
            attempts=attempts,
            validation=validation,
            evaluation_report=evaluation.model_dump() if evaluation is not None else {},
        )

    def _select_associated_skill(self, state: AgentState) -> str | None:
        """从当前计划和执行结果中提取实际关联的 Skill。"""
        for step in state.get("execution_results", []):
            tool_args = step.get("tool_args") or {}
            if isinstance(tool_args, dict) and tool_args.get("skill_name"):
                return str(tool_args["skill_name"])

        plan_model = state.get("plan_model")
        steps = getattr(plan_model, "steps", None)
        if isinstance(steps, list):
            for step in steps:
                tool_args = getattr(step, "tool_args", None) or {}
                if isinstance(tool_args, dict) and tool_args.get("skill_name"):
                    return str(tool_args["skill_name"])

        plan = state.get("plan")
        if plan is not None:
            for step in plan.get("steps", []):
                tool_args = step.get("tool_args") or {}
                if isinstance(tool_args, dict) and tool_args.get("skill_name"):
                    return str(tool_args["skill_name"])

        return None

    def _build_final_result(
        self,
        state: AgentState,
        validation: ValidationRecord,
        evaluation: EvaluationReport | None,
        learned_skill: str | None,
        trajectory_path: str,
    ) -> str:
        """拼装给用户返回的最终分析结果。"""
        executor_results = state.get("executor_results", [])
        output_files: list[str] = []
        for result in executor_results:
            artifacts = getattr(result, "artifacts", {}) or {}
            output_files.extend(str(path) for path in artifacts.get("output_files", []))

        report_path = next((Path(path) for path in output_files if Path(path).name == "analysis_report.md"), None)
        lines = ["# 数据分析执行结果", ""]

        if report_path and report_path.exists():
            report = report_path.read_text(encoding="utf-8", errors="replace")
            lines.append(report[:12000])
        elif executor_results:
            lines.append(str(getattr(executor_results[-1], "output", "")))

        lines.extend(["", "## 验证结果"])
        if validation.passed:
            lines.append("- 通过：代码执行成功，且生成了报告与结构化结果。")
        else:
            lines.extend(f"- {issue}" for issue in validation.issues)

        if output_files:
            lines.extend(["", "## 输出文件"])
            lines.extend(f"- {path}" for path in sorted(set(output_files)))

        lines.extend(["", "## 自学习"])
        if learned_skill:
            lines.append(f"- 已学习并注册 Skill：{learned_skill}")
        elif validation.passed:
            lines.append("- 本次分析成功，但未生成新的 Skill。")
        else:
            lines.append("- 本次分析未通过验证，不写入可复用 Skill。")
        lines.append(f"- 轨迹文件：{trajectory_path}")

        return "\n".join(lines)

    def _write_memory_records(
        self,
        *,
        state: AgentState,
        validation: ValidationRecord,
        evaluation: EvaluationReport | None,
        final_result: str,
        learned_skill: str | None,
        trajectory: AnalysisTrajectory,
    ) -> None:
        """把本次任务沉淀到长期记忆。"""
        if self._memory_manager is None:
            return

        with suppress(Exception):
            self._memory_manager.add_memory(
                messages=[
                    {"role": "user", "content": state["user_query"]},
                    {"role": "assistant", "content": final_result[:4000]},
                ],
                user_id=self._user_id,
                session_id=state.get("session_id"),
                metadata={
                    "type": "conversation",
                    "intent": state.get("intent", ""),
                    "passed": validation.passed,
                    "evaluation_score": evaluation.final_score if evaluation is not None else 0.0,
                    "task_family": evaluation.task_family if evaluation is not None else state.get("intent", ""),
                    "trajectory_id": trajectory.trajectory_id,
                    "learned_skill": learned_skill or "",
                    "selected_skill": self._select_associated_skill(state) or "",
                },
            )

        with suppress(Exception):
            if validation.passed:
                method = learned_skill or state.get("intent") or "data_analysis"
                self._memory_manager.record_analysis_method(
                    user_id=self._user_id,
                    method=method,
                    context=state["user_query"][:200],
                )

        with suppress(Exception):
            workspace = state.get("workspace", {})
            input_files = [Path(str(path)) for path in workspace.get("input_files", [])]
            if input_files:
                suffixes = [path.suffix.lower() or "unknown" for path in input_files]
                characteristics = f"{len(input_files)} 个输入文件，类型: {', '.join(sorted(set(suffixes)))}"
                self._memory_manager.record_data_characteristics(
                    user_id=self._user_id,
                    characteristics=characteristics,
                    data_type=",".join(sorted(set(suffixes))),
                )

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
        return self._compile_with_checkpointer(self._checkpointer)

    def _compile_with_checkpointer(self, checkpointer: Any | None = None) -> Any:
        """使用指定 checkpointer 编译工作流。"""
        if self._workflow is None:
            self.build_workflow()

        assert self._workflow is not None
        active_checkpointer = checkpointer or self._checkpointer or MemorySaver()
        self._checkpointer = active_checkpointer
        self._compiled_workflow = self._workflow.compile(checkpointer=active_checkpointer)
        self._compiled_checkpointer_id = id(active_checkpointer)
        return self._compiled_workflow

    async def ensure_compiled(self) -> Any:
        """确保工作流使用持久化 checkpointer 编译。"""
        checkpointer = await get_workflow_checkpoint_manager().get_checkpointer()
        if (
            self._compiled_workflow is None
            or self._compiled_checkpointer_id != id(checkpointer)
        ):
            return self._compile_with_checkpointer(checkpointer)
        return self._compiled_workflow

    async def get_state_snapshot(self, thread_id: str) -> StateSnapshot | None:
        """获取指定线程的持久化状态快照。"""
        await self.ensure_compiled()
        assert self._compiled_workflow is not None

        try:
            snapshot = await self._compiled_workflow.aget_state(
                {"configurable": {"thread_id": thread_id}}
            )
        except Exception:
            return None

        if snapshot is None:
            return None
        if not snapshot.values and not snapshot.next:
            return None
        return cast(StateSnapshot, snapshot)

    async def get_checkpoint_status(self, thread_id: str) -> dict[str, Any]:
        """返回线程的 checkpoint 状态。"""
        snapshot = await self.get_state_snapshot(thread_id)
        if snapshot is None:
            return {
                "available": False,
                "resumable": False,
                "next_nodes": [],
                "created_at": None,
                "config": {},
                "summary": {},
            }

        state_values = cast(dict[str, Any], snapshot.values or {})
        return {
            "available": True,
            "resumable": bool(snapshot.next),
            "next_nodes": list(snapshot.next),
            "created_at": snapshot.created_at,
            "config": dict(snapshot.config or {}),
            "summary": {
                "intent": state_values.get("intent", ""),
                "iteration_count": state_values.get("iteration_count", 0),
                "final_result": state_values.get("final_result", ""),
                "has_plan": state_values.get("plan") is not None,
            },
        }

    async def resume(
        self,
        thread_id: str,
        *,
        interrupt_before: list[str] | None = None,
        interrupt_after: list[str] | None = None,
    ) -> AgentState:
        """从持久化 checkpoint 恢复执行。"""
        await self.ensure_compiled()
        assert self._compiled_workflow is not None
        config = {"configurable": {"thread_id": thread_id}}
        result = await self._compiled_workflow.ainvoke(
            None,
            config,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            durability=self._durability_mode,
        )
        return cast(AgentState, result)

    async def run(
        self,
        user_query: str,
        thread_id: str = "default",
        context: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
        *,
        interrupt_before: list[str] | None = None,
        interrupt_after: list[str] | None = None,
    ) -> AgentState:
        """运行工作流

        Args:
            user_query: 用户查询
            thread_id: 线程 ID（用于状态持久化）

        Returns:
            最终状态
        """
        await self.ensure_compiled()

        assert self._compiled_workflow is not None
        effective_context = user_context if user_context is not None else context
        workspace = self._prepare_workspace(thread_id, user_query, effective_context or {})
        initial_state = create_initial_state(
            user_query,
            user_context=effective_context,
            session_id=thread_id,
        )
        initial_state["workspace"] = workspace
        config = {"configurable": {"thread_id": thread_id}}

        result = await self._compiled_workflow.ainvoke(
            initial_state,
            config,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            durability=self._durability_mode,
        )
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
    user_id: str = "default",
) -> AgentWorkflow:
    """创建工作流实例

    Args:
        llm: LLM 实例
        intent_recognizer: 意图识别器实例
        user_id: 用户 ID

    Returns:
        工作流实例
    """
    return AgentWorkflow(llm=llm, intent_recognizer=intent_recognizer, user_id=user_id)
