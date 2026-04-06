"""技能数据模型

定义技能的标准数据结构。
"""

from typing import Any

from pydantic import BaseModel, Field


class SkillParameter(BaseModel):
    """技能参数定义"""

    name: str = Field(..., description="参数名称")
    type: str = Field(default="string", description="参数类型")
    description: str = Field(default="", description="参数描述")
    required: bool = Field(default=True, description="是否必需")
    default: Any = Field(default=None, description="默认值")
    enum: list[str] | None = Field(default=None, description="枚举值列表")


class SkillMetadata(BaseModel):
    """技能元数据"""

    name: str = Field(..., description="技能名称")
    version: str = Field(default="1.0.0", description="版本号")
    description: str = Field(default="", description="技能描述")
    author: str = Field(default="", description="作者")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    category: str = Field(default="general", description="技能类别")
    min_python_version: str = Field(default="3.10", description="最低 Python 版本")
    dependencies: list[str] = Field(default_factory=list, description="依赖包列表")


class SkillExample(BaseModel):
    """技能使用示例"""

    name: str = Field(default="", description="示例名称")
    description: str = Field(default="", description="示例描述")
    input: dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output: str | dict[str, Any] | None = Field(default=None, description="预期输出")


class Skill(BaseModel):
    """技能完整定义"""

    metadata: SkillMetadata = Field(..., description="技能元数据")
    parameters: list[SkillParameter] = Field(default_factory=list, description="参数列表")
    prompt_template: str = Field(default="", description="提示词模板")
    examples: list[SkillExample] = Field(default_factory=list, description="使用示例")
    notes: list[str] = Field(default_factory=list, description="注意事项")
    source_path: str | None = Field(default=None, description="源文件路径")

    @property
    def name(self) -> str:
        """技能名称"""
        return self.metadata.name

    @property
    def description(self) -> str:
        """技能描述"""
        return self.metadata.description

    def get_required_parameters(self) -> list[SkillParameter]:
        """获取必需参数列表"""
        return [p for p in self.parameters if p.required]

    def get_optional_parameters(self) -> list[SkillParameter]:
        """获取可选参数列表"""
        return [p for p in self.parameters if not p.required]

    def render_prompt(self, **kwargs: Any) -> str:
        """渲染提示词模板

        Args:
            **kwargs: 模板参数

        Returns:
            渲染后的提示词
        """
        prompt = self.prompt_template
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))
        return prompt

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """验证参数

        Args:
            params: 参数字典

        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []
        param_names = {p.name for p in self.parameters}

        for required_param in self.get_required_parameters():
            if required_param.name not in params:
                errors.append(f"缺少必需参数: {required_param.name}")

        for param_name in params:
            if param_name not in param_names:
                errors.append(f"未知参数: {param_name}")

        return len(errors) == 0, errors

    def to_openai_tool_definition(self) -> dict[str, Any]:
        """转换为 OpenAI 工具定义格式

        Returns:
            OpenAI 工具定义字典
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

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
