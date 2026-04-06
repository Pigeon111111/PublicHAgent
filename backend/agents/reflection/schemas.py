"""Reflection Agent 结构化输出格式

使用 Pydantic 定义反思评估相关的数据结构。
"""

from enum import Enum

from pydantic import BaseModel, Field


class QualityLevel(str, Enum):
    """质量等级"""

    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"


class ReflectionResult(BaseModel):
    """反思结果"""

    should_replan: bool = Field(description="是否需要重新规划")
    feedback: str = Field(description="反馈意见")
    quality_score: float = Field(description="质量评分，范围 0-1", ge=0, le=1)
    quality_level: QualityLevel = Field(description="质量等级", default=QualityLevel.ACCEPTABLE)
    suggestions: list[str] = Field(description="改进建议", default_factory=list)
    strengths: list[str] = Field(description="执行优点", default_factory=list)
    weaknesses: list[str] = Field(description="执行不足", default_factory=list)


class EvaluationCriteria(BaseModel):
    """评估标准"""

    correctness: float = Field(description="正确性评分", ge=0, le=1, default=0.5)
    completeness: float = Field(description="完整性评分", ge=0, le=1, default=0.5)
    efficiency: float = Field(description="效率评分", ge=0, le=1, default=0.5)
    clarity: float = Field(description="清晰度评分", ge=0, le=1, default=0.5)


class StepEvaluation(BaseModel):
    """步骤评估"""

    step_id: str = Field(description="步骤 ID")
    success: bool = Field(description="是否成功")
    output_quality: float = Field(description="输出质量评分", ge=0, le=1)
    issues: list[str] = Field(description="问题列表", default_factory=list)
