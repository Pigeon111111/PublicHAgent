"""Executor Agent 实现

提供代码生成、沙箱执行、Reflection 循环能力。
使用 with_structured_output 确保结构化输出。
支持上下文隔离，只获取必要信息。
"""

import asyncio
import time
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.base.llm_client import LLMClient, invoke_structured_output
from backend.agents.executor.context import IsolatedExecutionContext
from backend.agents.executor.schemas import (
    CodeFixRequest,
    CodeFixResult,
    ExecutionResult,
    GeneratedCode,
)
from backend.agents.planner.schemas import ExecutionStep
from backend.sandbox.safe_executor import (
    SafeCodeExecutor,
    SafeExecutionContext,
)
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

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        user_id: str = "default",
        safe_executor: SafeCodeExecutor | None = None,
    ) -> None:
        """初始化 Executor Agent

        Args:
            llm: LLM 实例，如果为 None 则使用默认 LLM
            user_id: 用户 ID，用于获取用户配置的模型
        """
        self._llm = llm
        self._llm_client: LLMClient | None = None
        self._execution_context: dict[str, Any] = {}
        self._user_id = user_id
        self._safe_executor = safe_executor or self._create_default_safe_executor(user_id)

    def _get_llm(self) -> BaseChatModel:
        """获取 LLM 实例"""
        if self._llm is not None:
            return self._llm
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client.get_executor_llm(self._user_id)

    def set_context(self, context: dict[str, Any]) -> None:
        """设置执行上下文

        Args:
            context: 执行上下文
        """
        self._execution_context = context

    def set_safe_executor(self, safe_executor: SafeCodeExecutor) -> None:
        """设置受限代码执行器。"""
        self._safe_executor = safe_executor

    def _create_default_safe_executor(self, user_id: str) -> SafeCodeExecutor:
        """创建默认受限执行器，供单元测试和无会话调用使用。"""
        safe_user_id = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in user_id)
        root = Path("data/sessions") / (safe_user_id or "default")
        input_dir = root / "input"
        workspace_dir = root / "workspace"
        output_dir = root / "output"
        for directory in (input_dir, workspace_dir, output_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return SafeCodeExecutor(
            SafeExecutionContext(
                session_id=safe_user_id or "default",
                input_dir=input_dir,
                workspace_dir=workspace_dir,
                output_dir=output_dir,
                input_files=[],
            )
        )

    async def generate_code(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | IsolatedExecutionContext | None = None,
    ) -> GeneratedCode:
        """根据步骤生成代码

        Args:
            step: 执行步骤
            context: 执行上下文（字典或隔离上下文）

        Returns:
            生成的代码
        """
        if step.tool_args.get("prefer_fallback"):
            return self._generate_fallback_code(step, context)

        context_str = ""
        if isinstance(context, IsolatedExecutionContext):
            context_str = f"""
当前步骤: {context.step_index + 1}/{context.total_steps}
上一步结果: {context.previous_result[:500] if context.previous_result else '无'}
预期输出: {context.required_output}
"""
        elif context:
            context_str = f"\n执行上下文:\n{self._format_context(context)}"

        user_message = f"""步骤描述: {step.description}
预期输出: {step.expected_output}
工具名称: {step.tool_name}
工具参数: {step.tool_args}
{context_str}

请生成 Python 代码来执行此步骤。"""

        try:
            llm = self._get_llm()
            result = await asyncio.wait_for(
                invoke_structured_output(
                    llm,
                    [
                        SystemMessage(content=self.CODE_GENERATION_PROMPT),
                        HumanMessage(content=user_message),
                    ],
                    GeneratedCode,
                ),
                timeout=30,
            )

            if isinstance(result, GeneratedCode):
                return result
        except Exception:
            pass

        return self._generate_fallback_code(step, context)

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
        try:
            llm = self._get_llm()
        except Exception:
            return CodeFixResult(
                fixed_code=request.original_code,
                fix_explanation="LLM 不可用，保留原代码",
            )

        user_message = self.CODE_FIX_PROMPT.format(
            code=request.original_code,
            error=request.error_message,
        )

        result = await asyncio.wait_for(
            invoke_structured_output(
                llm,
                [
                    SystemMessage(content="你是一个 Python 代码调试专家。"),
                    HumanMessage(content=user_message),
                ],
                CodeFixResult,
            ),
            timeout=30,
        )

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

        if self._safe_executor is None:
            return ExecutionResult(
                success=False,
                output="",
                error="未配置受限代码执行器，拒绝在宿主机直接执行代码",
                code=code,
                execution_time=0.0,
            )

        result = self._safe_executor.execute(code, timeout=timeout)
        return ExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            code=result.code,
            execution_time=result.execution_time,
            artifacts=result.artifacts,
        )

    async def execute_step(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | IsolatedExecutionContext | None = None,
    ) -> ExecutionResult:
        """执行步骤（带 Reflection 循环）

        Args:
            step: 执行步骤
            context: 执行上下文（字典或隔离上下文）

        Returns:
            执行结果
        """
        if step.tool_name and step.tool_name not in ["python_code", ""]:
            return await self._execute_with_tool(step, context)

        generated_code = await self.generate_code(step, context)
        code = self._prepare_code(generated_code)

        for attempt in range(self.MAX_RETRIES):
            result = await asyncio.to_thread(self.execute_code, code)

            if result.success:
                return result

            if attempt < self.MAX_RETRIES - 1:
                context_dict = context.to_dict() if isinstance(context, IsolatedExecutionContext) else context
                fix_request = CodeFixRequest(
                    original_code=code,
                    error_message=result.error,
                    attempt=attempt + 1,
                    context=context_dict or {},
                )
                fix_result = await self.fix_code(fix_request)
                code = fix_result.fixed_code

        return result

    async def _execute_with_tool(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | IsolatedExecutionContext | None = None,
    ) -> ExecutionResult:
        """使用注册的工具执行步骤

        Args:
            step: 执行步骤
            context: 执行上下文（字典或隔离上下文）

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

    def _generate_fallback_code(
        self,
        step: ExecutionStep,
        context: dict[str, Any] | IsolatedExecutionContext | None = None,
    ) -> GeneratedCode:
        """生成无需 LLM 的数据分析回退代码。"""
        analysis_method = str(step.tool_args.get("analysis_method") or step.description)
        analysis_type = str(step.tool_args.get("analysis_type") or "auto")

        code = f'''
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy import stats

input_dir = Path(PH_INPUT_DIR)
output_dir = Path(PH_OUTPUT_DIR)
output_dir.mkdir(parents=True, exist_ok=True)


def to_jsonable(value):
    """把 pandas/numpy 值转换成标准 JSON 可写入的类型。"""
    if isinstance(value, dict):
        return {{str(key): to_jsonable(item) for key, item in value.items()}}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if pd.isna(value):
        return None
    return value


data_files = [Path(path) for path in PH_INPUT_FILES]
if not data_files:
    data_files = [
        path for path in input_dir.iterdir()
        if path.suffix.lower() in [".csv", ".xlsx", ".xls", ".json", ".parquet", ".feather"]
    ]
if not data_files:
    raise ValueError("没有可分析的数据文件，请先上传 CSV、Excel、JSON、Parquet 或 Feather 文件")

data_file = data_files[0]
suffix = data_file.suffix.lower()
if suffix == ".csv":
    df = pd.read_csv(data_file)
elif suffix in [".xlsx", ".xls"]:
    df = pd.read_excel(data_file)
elif suffix == ".json":
    df = pd.read_json(data_file)
elif suffix == ".parquet":
    df = pd.read_parquet(data_file)
elif suffix == ".feather":
    df = pd.read_feather(data_file)
else:
    raise ValueError(f"不支持的数据文件类型: {{suffix}}")

numeric_df = df.select_dtypes(include=[np.number])
result = {{
    "analysis_method": {analysis_method!r},
    "analysis_type": {analysis_type!r},
    "source_file": str(data_file),
    "shape": {{"rows": int(df.shape[0]), "columns": int(df.shape[1])}},
    "columns": [str(col) for col in df.columns],
    "missing_values": {{str(col): int(df[col].isna().sum()) for col in df.columns}},
    "preview": df.head(10).to_dict(orient="records"),
}}

if not numeric_df.empty:
    description = numeric_df.describe()
    result["descriptive_statistics"] = description.to_dict()
    if numeric_df.shape[1] > 1:
        result["correlation_matrix"] = numeric_df.corr(numeric_only=True).to_dict()
    normality = {{}}
    for col in numeric_df.columns:
        values = numeric_df[col].dropna()
        if 3 <= len(values) <= 5000:
            statistic, p_value = stats.shapiro(values)
            normality[str(col)] = {{"statistic": statistic, "p_value": p_value}}
    result["normality_tests"] = normality
else:
    result["message"] = "数据中没有数值列，已输出结构、字段和缺失值摘要"

result = to_jsonable(result)
json_path = output_dir / "analysis_result.json"
json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

report_lines = [
    "# 数据分析报告",
    "",
    f"分析方法: {{result['analysis_method']}}",
    f"数据文件: {{data_file.name}}",
    f"数据规模: {{df.shape[0]}} 行，{{df.shape[1]}} 列",
    "",
    "## 字段",
    ", ".join(str(col) for col in df.columns),
    "",
    "## 缺失值",
]
for col, count in result["missing_values"].items():
    report_lines.append(f"- {{col}}: {{count}}")

if not numeric_df.empty:
    report_lines.extend([
        "",
        "## 数值变量描述性统计",
        "```",
        numeric_df.describe().to_string(),
        "```",
    ])
    if numeric_df.shape[1] > 1:
        report_lines.extend([
            "",
            "## 相关矩阵",
            "```",
            numeric_df.corr(numeric_only=True).to_string(),
            "```",
        ])
else:
    report_lines.extend(["", result.get("message", "")])

report_lines.extend(["", f"结构化结果已保存: {{json_path}}"])
report_path = output_dir / "analysis_report.md"
report_path.write_text("\\n".join(report_lines), encoding="utf-8")

print("\\n".join(report_lines))
'''
        return GeneratedCode(
            code=code,
            explanation="LLM 不可用或输出无效时，使用通用数据分析回退逻辑",
            imports=[],
        )

        code = f'''
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy import stats

input_dir = Path(PH_INPUT_DIR)
output_dir = Path(PH_OUTPUT_DIR)
output_dir.mkdir(parents=True, exist_ok=True)

data_files = [Path(path) for path in PH_INPUT_FILES]
if not data_files:
    data_files = [path for path in input_dir.iterdir() if path.suffix.lower() in [".csv", ".xlsx", ".xls", ".json"]]
if not data_files:
    raise ValueError("没有可分析的数据文件，请先上传 CSV、Excel 或 JSON 文件")

data_file = data_files[0]
suffix = data_file.suffix.lower()
if suffix == ".csv":
    df = pd.read_csv(data_file)
elif suffix in [".xlsx", ".xls"]:
    df = pd.read_excel(data_file)
elif suffix == ".json":
    df = pd.read_json(data_file)
else:
    raise ValueError(f"不支持的数据文件类型: {{suffix}}")

numeric_df = df.select_dtypes(include=[np.number])
result = {{
    "analysis_method": {analysis_method!r},
    "analysis_type": {analysis_type!r},
    "source_file": str(data_file),
    "shape": {{"rows": int(df.shape[0]), "columns": int(df.shape[1])}},
    "columns": list(df.columns),
    "missing_values": {{col: int(df[col].isna().sum()) for col in df.columns}},
    "preview": df.head(10).to_dict(orient="records"),
}}

if not numeric_df.empty:
    result["descriptive_statistics"] = numeric_df.describe().replace({{np.nan: None}}).to_dict()
    result["correlation_matrix"] = numeric_df.corr().replace({{np.nan: None}}).to_dict()
    normality = {{}}
    for col in numeric_df.columns:
        values = numeric_df[col].dropna()
        if 3 <= len(values) <= 5000:
            statistic, p_value = stats.shapiro(values)
            normality[col] = {{"statistic": float(statistic), "p_value": float(p_value)}}
    result["normality_tests"] = normality
else:
    result["message"] = "数据中没有数值列，已输出结构和缺失值摘要"

json_path = output_dir / "analysis_result.json"
json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

report_lines = [
    "# 数据分析报告",
    "",
    f"分析方法: {{result['analysis_method']}}",
    f"数据文件: {{data_file.name}}",
    f"数据规模: {{df.shape[0]}} 行，{{df.shape[1]}} 列",
    "",
    "## 字段",
    ", ".join(str(col) for col in df.columns),
    "",
    "## 缺失值",
]
for col, count in result["missing_values"].items():
    report_lines.append(f"- {{col}}: {{count}}")
if "descriptive_statistics" in result:
    report_lines.extend(["", "## 数值变量描述性统计", "```", numeric_df.describe().to_string(), "```"])
report_lines.extend(["", f"结构化结果已保存: {{json_path}}"])

report_path = output_dir / "analysis_report.md"
report_path.write_text("\\n".join(report_lines), encoding="utf-8")

print("\\n".join(report_lines))
'''
        return GeneratedCode(
            code=code,
            explanation="LLM 不可用或输出无效时，使用通用数据分析回退逻辑",
            imports=[],
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
