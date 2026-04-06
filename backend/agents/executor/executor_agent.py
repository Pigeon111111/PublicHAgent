"""Executor Agent 实现

提供代码生成、沙箱执行、Reflection 循环能力。
使用 with_structured_output 确保结构化输出。
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.base.llm_client import LLMClient
from backend.agents.executor.schemas import (
    CodeFixRequest,
    CodeFixResult,
    ExecutionResult,
    GeneratedCode,
)
from backend.agents.planner.schemas import ExecutionStep
from backend.tools.registry import get_tool_registry


class ExecutorAgent:
    """执行 Agent

    负责根据步骤生成 Python 代码，在沙箱环境中执行，
    并支持 Reflection 循环（最多 3 次尝试）。
    """

    MAX_RETRIES = 3
    EXECUTION_TIMEOUT = 60

    CODE_GENERATION_PROMPT = """你是一个公共卫生数据分析专家和 Python 程序员。
根据给定的步骤描述，生成高质量的 Python 代码来执行该任务。

要求：
1. 代码应该简洁、高效、可读
2. 包含必要的错误处理
3. 使用标准的数据分析库（pandas, numpy, scipy, matplotlib 等）
4. 代码应该能够独立运行
5. 输出结果应该清晰明了"""

    CODE_FIX_PROMPT = """代码执行出错，需要修复。

原始代码:
```python
{code}
```

错误信息:
{error}

请分析错误原因并修复代码。修复时注意：
1. 检查语法错误
2. 检查变量名和函数名
3. 检查数据类型
4. 检查导入语句
5. 添加必要的错误处理"""

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """初始化 Executor Agent

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._execution_context: dict[str, Any] = {}

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_default_llm()

    def set_context(self, context: dict[str, Any]) -> None:
        """设置执行上下文

        Args:
            context: 执行上下文
        """
        self._execution_context = context

    async def generate_code(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | None = None,
    ) -> GeneratedCode:
        """根据步骤生成代码

        Args:
            step: 执行步骤
            context: 执行上下文

        Returns:
            生成的代码
        """
        llm = self._get_llm()

        context_str = ""
        if context:
            context_str = f"\n执行上下文:\n{self._format_context(context)}"

        user_message = f"""步骤描述: {step.description}
预期输出: {step.expected_output}
工具名称: {step.tool_name}
工具参数: {step.tool_args}
{context_str}

请生成 Python 代码来执行此步骤。"""

        structured_llm = llm.with_structured_output(GeneratedCode)
        result = await structured_llm.ainvoke([
            SystemMessage(content=self.CODE_GENERATION_PROMPT),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, GeneratedCode):
            return result

        return GeneratedCode(
            code="# 代码生成失败\npass",
            explanation="代码生成失败",
            imports=[],
        )

    async def fix_code(
        self,
        request: CodeFixRequest,
    ) -> CodeFixResult:
        """修复错误的代码

        Args:
            request: 代码修复请求

        Returns:
            修复结果
        """
        llm = self._get_llm()

        user_message = self.CODE_FIX_PROMPT.format(
            code=request.original_code,
            error=request.error_message,
        )

        structured_llm = llm.with_structured_output(CodeFixResult)
        result = await structured_llm.ainvoke([
            SystemMessage(content="你是一个 Python 代码调试专家。"),
            HumanMessage(content=user_message),
        ])

        if isinstance(result, CodeFixResult):
            return result

        return CodeFixResult(
            fixed_code=request.original_code,
            fix_explanation="无法修复代码",
        )

    def execute_code(
        self,
        code: str,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在本地环境中执行代码

        Args:
            code: 要执行的代码
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        if timeout is None:
            timeout = self.EXECUTION_TIMEOUT

        start_time = time.time()

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(Path(temp_path).parent),
                )

                execution_time = time.time() - start_time

                if result.returncode == 0:
                    return ExecutionResult(
                        success=True,
                        output=result.stdout,
                        error="",
                        code=code,
                        execution_time=execution_time,
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        output=result.stdout,
                        error=result.stderr,
                        code=code,
                        execution_time=execution_time,
                    )
            finally:
                Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                error=f"执行超时（{timeout}秒）",
                code=code,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                code=code,
                execution_time=execution_time,
            )

    async def execute_step(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """执行步骤（带 Reflection 循环）

        Args:
            step: 执行步骤
            context: 执行上下文

        Returns:
            执行结果
        """
        if step.tool_name and step.tool_name not in ["python_code", ""]:
            return await self._execute_with_tool(step, context)

        generated_code = await self.generate_code(step, context)
        code = self._prepare_code(generated_code)

        for attempt in range(self.MAX_RETRIES):
            result = self.execute_code(code)

            if result.success:
                return result

            if attempt < self.MAX_RETRIES - 1:
                fix_request = CodeFixRequest(
                    original_code=code,
                    error_message=result.error,
                    attempt=attempt + 1,
                    context=context or {},
                )
                fix_result = await self.fix_code(fix_request)
                code = fix_result.fixed_code

        return result

    async def _execute_with_tool(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """使用注册的工具执行步骤

        Args:
            step: 执行步骤
            context: 执行上下文

        Returns:
            执行结果
        """
        start_time = time.time()

        try:
            registry = get_tool_registry()
            result = registry.execute(step.tool_name, **step.tool_args)
            execution_time = time.time() - start_time

            return ExecutionResult(
                success=True,
                output=str(result),
                error="",
                code=f"# 使用工具: {step.tool_name}\n# 参数: {step.tool_args}",
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                code=f"# 使用工具: {step.tool_name}\n# 参数: {step.tool_args}",
                execution_time=execution_time,
            )

    def _prepare_code(self, generated_code: GeneratedCode) -> str:
        """准备完整代码（添加导入语句）

        Args:
            generated_code: 生成的代码

        Returns:
            完整代码
        """
        imports = "\n".join(generated_code.imports)
        if imports:
            return f"{imports}\n\n{generated_code.code}"
        return generated_code.code

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

    def get_execution_summary(self, results: list[ExecutionResult]) -> str:
        """获取执行摘要

        Args:
            results: 执行结果列表

        Returns:
            执行摘要字符串
        """
        if not results:
            return "无执行结果"

        success_count = sum(1 for r in results if r.success)
        total_time = sum(r.execution_time for r in results)

        return f"""执行摘要:
总步骤数: {len(results)}
成功: {success_count}
失败: {len(results) - success_count}
总耗时: {total_time:.2f}秒"""
