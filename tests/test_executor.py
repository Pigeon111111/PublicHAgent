"""Executor Agent 单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.executor import ExecutionResult, ExecutorAgent, GeneratedCode
from backend.agents.executor.schemas import CodeFixRequest, CodeFixResult
from backend.agents.planner.schemas import ExecutionStep


class TestGeneratedCode:
    """测试生成代码模型"""

    def test_generated_code_creation(self) -> None:
        """测试创建生成代码"""
        code = GeneratedCode(
            code="print('hello')",
            explanation="打印 hello",
            imports=["import pandas as pd"],
        )
        assert code.code == "print('hello')"
        assert code.explanation == "打印 hello"
        assert code.imports == ["import pandas as pd"]

    def test_generated_code_defaults(self) -> None:
        """测试生成代码默认值"""
        code = GeneratedCode(
            code="pass",
            explanation="空代码",
        )
        assert code.imports == []


class TestExecutionResult:
    """测试执行结果模型"""

    def test_execution_result_success(self) -> None:
        """测试成功执行结果"""
        result = ExecutionResult(
            success=True,
            output="执行成功",
            error="",
            code="print('hello')",
            execution_time=0.5,
        )
        assert result.success is True
        assert result.output == "执行成功"
        assert result.error == ""
        assert result.execution_time == 0.5

    def test_execution_result_failure(self) -> None:
        """测试失败执行结果"""
        result = ExecutionResult(
            success=False,
            output="",
            error="NameError: name 'x' is not defined",
            code="print(x)",
            execution_time=0.1,
        )
        assert result.success is False
        assert result.error == "NameError: name 'x' is not defined"


class TestExecutorAgent:
    """测试 Executor Agent"""

    def test_init_without_llm(self) -> None:
        """测试不带 LLM 初始化"""
        agent = ExecutorAgent()
        assert agent._llm is None
        assert agent._llm_client is None

    def test_init_with_llm(self) -> None:
        """测试带 LLM 初始化"""
        mock_llm = MagicMock()
        agent = ExecutorAgent(llm=mock_llm)
        assert agent._llm == mock_llm

    def test_set_context(self) -> None:
        """测试设置上下文"""
        agent = ExecutorAgent()
        agent.set_context({"data": "test.csv"})
        assert agent._execution_context == {"data": "test.csv"}

    def test_execute_code_success(self) -> None:
        """测试成功执行代码"""
        agent = ExecutorAgent()
        code = "print('hello world')"
        result = agent.execute_code(code)
        assert result.success is True
        assert "hello world" in result.output

    def test_execute_code_failure(self) -> None:
        """测试失败执行代码"""
        agent = ExecutorAgent()
        code = "raise ValueError('test error')"
        result = agent.execute_code(code)
        assert result.success is False
        assert "test error" in result.error

    def test_execute_code_timeout(self) -> None:
        """测试执行超时"""
        agent = ExecutorAgent()
        code = "import time; time.sleep(10)"
        result = agent.execute_code(code, timeout=1)
        assert result.success is False
        assert "超时" in result.error

    def test_prepare_code_with_imports(self) -> None:
        """测试准备代码（带导入）"""
        agent = ExecutorAgent()
        generated = GeneratedCode(
            code="df = pd.DataFrame()",
            explanation="创建 DataFrame",
            imports=["import pandas as pd", "import numpy as np"],
        )
        prepared = agent._prepare_code(generated)
        assert "import pandas as pd" in prepared
        assert "import numpy as np" in prepared
        assert "df = pd.DataFrame()" in prepared

    def test_prepare_code_without_imports(self) -> None:
        """测试准备代码（无导入）"""
        agent = ExecutorAgent()
        generated = GeneratedCode(
            code="x = 1 + 1",
            explanation="简单计算",
        )
        prepared = agent._prepare_code(generated)
        assert prepared == "x = 1 + 1"

    def test_get_execution_summary(self) -> None:
        """测试获取执行摘要"""
        agent = ExecutorAgent()
        results = [
            ExecutionResult(success=True, output="成功1", error="", code="", execution_time=0.1),
            ExecutionResult(success=False, output="", error="错误", code="", execution_time=0.2),
        ]
        summary = agent.get_execution_summary(results)
        assert "总步骤数: 2" in summary
        assert "成功: 1" in summary
        assert "失败: 1" in summary


class TestExecutorAgentAsync:
    """测试 Executor Agent 异步方法"""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """创建 Mock LLM"""
        mock = MagicMock()

        code_structured = AsyncMock()
        code_structured.ainvoke = AsyncMock(return_value=GeneratedCode(
            code="print('generated code')",
            explanation="生成的代码",
            imports=[],
        ))

        fix_structured = AsyncMock()
        fix_structured.ainvoke = AsyncMock(return_value=CodeFixResult(
            fixed_code="print('fixed code')",
            fix_explanation="修复了错误",
        ))

        def mock_with_structured_output(model_class):
            if model_class == GeneratedCode:
                return code_structured
            elif model_class == CodeFixResult:
                return fix_structured
            return code_structured

        mock.with_structured_output = MagicMock(side_effect=mock_with_structured_output)
        return mock

    @pytest.mark.asyncio
    async def test_generate_code(self, mock_llm: MagicMock) -> None:
        """测试生成代码"""
        agent = ExecutorAgent(llm=mock_llm)
        step = ExecutionStep(
            step_id="step_1",
            description="打印 hello",
        )
        code = await agent.generate_code(step)
        assert code.code == "print('generated code')"

    @pytest.mark.asyncio
    async def test_fix_code(self, mock_llm: MagicMock) -> None:
        """测试修复代码"""
        agent = ExecutorAgent(llm=mock_llm)
        request = CodeFixRequest(
            original_code="print(x)",
            error_message="NameError: name 'x' is not defined",
            attempt=1,
        )
        result = await agent.fix_code(request)
        assert result.fixed_code == "print('fixed code')"

    @pytest.mark.asyncio
    async def test_execute_step_success(self, mock_llm: MagicMock) -> None:
        """测试执行步骤成功"""
        agent = ExecutorAgent(llm=mock_llm)
        step = ExecutionStep(
            step_id="step_1",
            description="打印 hello",
        )
        result = await agent.execute_step(step)
        assert result.success is True
        assert "generated code" in result.output


class TestCodeFixRequest:
    """测试代码修复请求模型"""

    def test_code_fix_request_creation(self) -> None:
        """测试创建代码修复请求"""
        request = CodeFixRequest(
            original_code="print(x)",
            error_message="NameError",
            attempt=1,
            context={"variables": []},
        )
        assert request.original_code == "print(x)"
        assert request.error_message == "NameError"
        assert request.attempt == 1


class TestCodeFixResult:
    """测试代码修复结果模型"""

    def test_code_fix_result_creation(self) -> None:
        """测试创建代码修复结果"""
        result = CodeFixResult(
            fixed_code="x = 1\nprint(x)",
            fix_explanation="添加了变量定义",
        )
        assert result.fixed_code == "x = 1\nprint(x)"
        assert result.fix_explanation == "添加了变量定义"
