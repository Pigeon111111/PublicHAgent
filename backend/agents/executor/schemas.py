"""Executor Agent 结构化输出格式

使用 Pydantic 定义执行相关的数据结构。
"""

from typing import Any

from pydantic import BaseModel, Field


class GeneratedCode(BaseModel):
    """生成的代码"""

    code: str = Field(description="生成的 Python 代码")
    explanation: str = Field(description="代码解释")
    imports: list[str] = Field(description="需要的导入语句", default_factory=list)


class ExecutionResult(BaseModel):
    """执行结果"""

    success: bool = Field(description="执行是否成功")
    output: str = Field(description="执行输出")
    error: str = Field(description="错误信息", default="")
    code: str = Field(description="执行的代码", default="")
    execution_time: float = Field(description="执行时间（秒）", default=0.0)
    artifacts: dict[str, Any] = Field(description="生成的产物（如文件路径）", default_factory=dict)
    attempts: int = Field(description="执行尝试次数", default=1)
    reflection: dict[str, Any] = Field(description="反思结果", default_factory=dict)


class CodeFixRequest(BaseModel):
    """代码修复请求"""

    original_code: str = Field(description="原始代码")
    error_message: str = Field(description="错误信息")
    attempt: int = Field(description="当前尝试次数")
    context: dict[str, Any] = Field(description="执行上下文", default_factory=dict)


class CodeFixResult(BaseModel):
    """代码修复结果"""

    fixed_code: str = Field(description="修复后的代码")
    fix_explanation: str = Field(description="修复说明")


class CodeReflection(BaseModel):
    """代码反思结果。"""

    accept: bool = Field(description="是否接受当前执行结果")
    reasoning: str = Field(description="反思结论")
    issues: list[str] = Field(description="发现的问题", default_factory=list)
    next_action: str = Field(description="下一步动作", default="")
