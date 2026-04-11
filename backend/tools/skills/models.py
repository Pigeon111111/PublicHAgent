"""Skill 数据模型。

定义 Skill 的标准数据结构，并补齐方法家族与细分变体相关元数据。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SUPPORTED_METHOD_FAMILIES = (
    "descriptive_analysis",
    "statistical_test",
    "regression_analysis",
    "survival_analysis",
    "epidemiology_analysis",
    "visualization",
    "general",
)

SkillLifecycleState = Literal["active", "candidate", "deprecated", "legacy"]


class SkillParameter(BaseModel):
    """Skill 参数定义。"""

    name: str = Field(..., description="参数名称")
    type: str = Field(default="string", description="参数类型")
    description: str = Field(default="", description="参数描述")
    required: bool = Field(default=True, description="是否必需")
    default: Any = Field(default=None, description="默认值")
    enum: list[str] | None = Field(default=None, description="枚举值列表")


class SkillMetadata(BaseModel):
    """Skill 元数据。"""

    name: str = Field(..., description="Skill 名称")
    version: str = Field(default="1.0.0", description="版本号")
    description: str = Field(default="", description="Skill 描述")
    author: str = Field(default="", description="作者")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    category: str = Field(default="general", description="技能类别")
    min_python_version: str = Field(default="3.10", description="最低 Python 版本")
    dependencies: list[str] = Field(default_factory=list, description="依赖包列表")
    analysis_domain: str = Field(default="general", description="分析领域")
    method_family: str = Field(default="general", description="方法家族")
    method_variant: str = Field(default="", description="细分方法")
    process_signature: str = Field(default="", description="分析流程签名")
    input_schema_signature: str = Field(default="", description="输入结构签名")
    verifier_family: str = Field(default="", description="对应评估器家族")
    provenance_trajectory_id: str = Field(default="", description="来源轨迹 ID")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="经验置信度")
    lifecycle_state: SkillLifecycleState = Field(default="active", description="生命周期状态")
    last_used_at: str = Field(default="", description="最近使用时间")
    usage_count: int = Field(default=0, ge=0, description="使用次数")
    verifier_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="验证通过率")

    @property
    def is_learned(self) -> bool:
        """是否为学习产生的 Skill。"""

        return self.category == "learned-analysis" or "learned" in self.tags

    @property
    def normalized_method_family(self) -> str:
        """返回受支持的方法家族。"""

        family = (self.method_family or "").strip() or "general"
        if family not in SUPPORTED_METHOD_FAMILIES:
            return "general"
        return family


class SkillExample(BaseModel):
    """Skill 使用示例。"""

    name: str = Field(default="", description="示例名称")
    description: str = Field(default="", description="示例描述")
    input: dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output: str | dict[str, Any] | None = Field(default=None, description="预期输出")


class SkillCapability(BaseModel):
    """Skill 能力描述。"""

    capability: str = Field(default="", description="能力范围描述")
    limitations: list[str] = Field(default_factory=list, description="限制条件")
    applicable_scenarios: list[str] = Field(default_factory=list, description="适用场景")


class Skill(BaseModel):
    """完整 Skill 定义。"""

    metadata: SkillMetadata = Field(..., description="Skill 元数据")
    capability: SkillCapability = Field(default_factory=SkillCapability, description="能力描述")
    parameters: list[SkillParameter] = Field(default_factory=list, description="参数列表")
    prompt_template: str = Field(default="", description="提示词模板")
    examples: list[SkillExample] = Field(default_factory=list, description="使用示例")
    notes: list[str] = Field(default_factory=list, description="注意事项")
    source_path: str | None = Field(default=None, description="源文件路径")

    @property
    def name(self) -> str:
        """Skill 名称。"""

        return self.metadata.name

    @property
    def description(self) -> str:
        """Skill 描述。"""

        return self.metadata.description

    def get_required_parameters(self) -> list[SkillParameter]:
        """获取必需参数列表。"""

        return [parameter for parameter in self.parameters if parameter.required]

    def get_optional_parameters(self) -> list[SkillParameter]:
        """获取可选参数列表。"""

        return [parameter for parameter in self.parameters if not parameter.required]

    def render_prompt(self, **kwargs: Any) -> str:
        """渲染提示词模板。"""

        prompt = self.prompt_template
        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """校验参数。"""

        errors: list[str] = []
        parameter_names = {parameter.name for parameter in self.parameters}

        for required_parameter in self.get_required_parameters():
            if required_parameter.name not in params:
                errors.append(f"缺少必需参数: {required_parameter.name}")

        for parameter_name in params:
            if parameter_name not in parameter_names:
                errors.append(f"未知参数: {parameter_name}")

        return len(errors) == 0, errors

    def to_openai_tool_definition(self) -> dict[str, Any]:
        """转换为 OpenAI 工具定义。"""

        properties: dict[str, Any] = {}
        required: list[str] = []

        for parameter in self.parameters:
            property_payload: dict[str, Any] = {
                "type": parameter.type,
                "description": parameter.description,
            }
            if parameter.enum:
                property_payload["enum"] = parameter.enum
            if parameter.default is not None:
                property_payload["default"] = parameter.default
            properties[parameter.name] = property_payload
            if parameter.required:
                required.append(parameter.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
