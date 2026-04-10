"""技能加载器

实现技能的动态加载和发现机制。
"""

import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from backend.tools.skills.models import (
    Skill,
    SkillCapability,
    SkillExample,
    SkillMetadata,
    SkillParameter,
)


class SkillLoaderError(Exception):
    """技能加载错误"""

    pass


class SkillLoader:
    """技能加载器

    支持从文件系统动态加载技能，支持按需加载和技能发现。
    """

    SKILL_FILE_NAME = "SKILL.md"

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        """初始化技能加载器

        Args:
            skills_dir: 技能目录路径，默认为 backend/tools/skills
        """
        if skills_dir:
            self._skills_dir = Path(skills_dir)
        else:
            self._skills_dir = Path(__file__).parent

        self._cache: dict[str, Skill] = {}

    def discover_skills(self) -> list[str]:
        """发现所有可用技能

        Returns:
            技能名称列表
        """
        skills: list[str] = []
        if not self._skills_dir.exists():
            return skills

        for item in self._skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / self.SKILL_FILE_NAME
                if skill_file.exists():
                    skills.append(item.name)

        return skills

    def load_skill(self, skill_name: str, use_cache: bool = True) -> Skill:
        """加载指定技能

        Args:
            skill_name: 技能名称（目录名）
            use_cache: 是否使用缓存

        Returns:
            Skill 对象

        Raises:
            SkillLoaderError: 技能加载失败
        """
        if use_cache and skill_name in self._cache:
            return self._cache[skill_name]

        skill_dir = self._skills_dir / skill_name
        skill_file = skill_dir / self.SKILL_FILE_NAME

        if not skill_file.exists():
            raise SkillLoaderError(f"技能文件不存在: {skill_file}")

        try:
            skill = self._parse_skill_file(skill_file)
            skill.source_path = str(skill_dir)
            self._cache[skill_name] = skill
            return skill
        except Exception as e:
            raise SkillLoaderError(f"解析技能文件失败: {skill_file}, 错误: {e}") from e

    def load_all_skills(self, use_cache: bool = True) -> list[Skill]:
        """加载所有技能

        Args:
            use_cache: 是否使用缓存

        Returns:
            Skill 对象列表
        """
        skills = []
        for skill_name in self.discover_skills():
            try:
                skill = self.load_skill(skill_name, use_cache)
                skills.append(skill)
            except SkillLoaderError:
                continue
        return skills

    def reload_skill(self, skill_name: str) -> Skill:
        """重新加载技能（清除缓存）

        Args:
            skill_name: 技能名称

        Returns:
            Skill 对象
        """
        if skill_name in self._cache:
            del self._cache[skill_name]
        return self.load_skill(skill_name, use_cache=False)

    def clear_cache(self) -> None:
        """清除所有缓存"""
        self._cache.clear()

    def _parse_skill_file(self, skill_file: Path) -> Skill:
        """解析技能文件

        Args:
            skill_file: 技能文件路径

        Returns:
            Skill 对象
        """
        content = skill_file.read_text(encoding="utf-8")
        return self._parse_skill_content(content)

    def _parse_skill_content(self, content: str) -> Skill:
        """解析技能内容

        支持的格式：
        - YAML front matter (---)
        - Markdown 标题结构

        Args:
            content: 技能文件内容

        Returns:
            Skill 对象
        """
        metadata = SkillMetadata(name="unknown")
        capability = SkillCapability()
        parameters: list[SkillParameter] = []
        prompt_template = ""
        examples: list[SkillExample] = []
        notes: list[str] = []

        if content.strip().startswith("---"):
            metadata, remaining = self._parse_yaml_frontmatter(content)
            sections = self._parse_markdown_sections(remaining)
        else:
            sections = self._parse_markdown_sections(content)

        if "capability" in sections:
            capability = self._parse_capability_section(sections["capability"])

        if "parameters" in sections:
            parameters = self._parse_parameters_section(sections["parameters"])

        if "prompt_template" in sections:
            prompt_template = sections["prompt_template"].strip()

        if "examples" in sections:
            examples = self._parse_examples_section(sections["examples"])

        if "notes" in sections:
            notes = self._parse_notes_section(sections["notes"])

        return Skill(
            metadata=metadata,
            capability=capability,
            parameters=parameters,
            prompt_template=prompt_template,
            examples=examples,
            notes=notes,
        )

    def _parse_yaml_frontmatter(self, content: str) -> tuple[SkillMetadata, str]:
        """解析 YAML front matter"""
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return SkillMetadata(name="unknown"), content

        yaml_content = match.group(1)
        remaining = match.group(2)

        try:
            data = yaml.safe_load(yaml_content)
            metadata = SkillMetadata(
                name=data.get("name", "unknown"),
                version=data.get("version", "1.0.0"),
                description=data.get("description", ""),
                author=data.get("author", ""),
                tags=data.get("tags", []),
                category=data.get("category", "general"),
                min_python_version=data.get("min_python_version", "3.10"),
                dependencies=data.get("dependencies", []),
            )
            return metadata, remaining
        except yaml.YAMLError:
            return SkillMetadata(name="unknown"), remaining

    def _parse_markdown_sections(self, content: str) -> dict[str, str]:
        """解析 Markdown 章节"""
        sections: dict[str, str] = {}
        current_section = None
        current_content: list[str] = []

        section_mapping = {
            "能力描述": "capability",
            "capability": "capability",
            "参数": "parameters",
            "parameters": "parameters",
            "提示词模板": "prompt_template",
            "prompt template": "prompt_template",
            "使用示例": "examples",
            "examples": "examples",
            "注意事项": "notes",
            "notes": "notes",
        }

        for line in content.split("\n"):
            header_match = re.match(r"^#+\s+(.+)$", line)
            if header_match:
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                header = header_match.group(1).strip().lower()
                current_section = section_mapping.get(header)
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _parse_parameters_section(self, content: str) -> list[SkillParameter]:
        """解析参数章节"""
        parameters = []
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("- ") or line.startswith("* "):
                param = self._parse_parameter_line(line[2:])
                if param:
                    parameters.append(param)
            elif line.startswith("|"):
                param = self._parse_parameter_table_row(line)
                if param:
                    parameters.append(param)

        return parameters

    def _parse_capability_section(self, content: str) -> SkillCapability:
        """解析能力描述章节"""
        capability_text = ""
        limitations: list[str] = []
        applicable_scenarios: list[str] = []

        current_section = None

        for line in content.split("\n"):
            line_stripped = line.strip()

            if line_stripped.startswith("**能力范围**") or line_stripped.startswith("能力范围"):
                current_section = "capability"
                if ":" in line_stripped:
                    capability_text = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("**限制条件**") or line_stripped.startswith("限制条件"):
                current_section = "limitations"
            elif line_stripped.startswith("**适用场景**") or line_stripped.startswith("适用场景"):
                current_section = "scenarios"
            elif current_section == "capability" and not capability_text:
                if line_stripped and not line_stripped.startswith("#"):
                    capability_text = line_stripped
            elif current_section == "limitations":
                if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                    limitations.append(line_stripped[2:])
            elif current_section == "scenarios":
                if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                    applicable_scenarios.append(line_stripped[2:])

        return SkillCapability(
            capability=capability_text,
            limitations=limitations,
            applicable_scenarios=applicable_scenarios,
        )

    def _parse_parameter_line(self, line: str) -> SkillParameter | None:
        """解析参数行"""
        match = re.match(
            r"`?(\w+)`?\s*[:：]\s*(.+)$",
            line
        )
        if not match:
            return None

        name = match.group(1)
        rest = match.group(2)

        param_type = "string"
        description = rest
        required = True
        default = None
        enum = None

        type_match = re.search(r"\((\w+)\)", rest)
        if type_match:
            param_type = type_match.group(1)
            description = re.sub(r"\(\w+\)", "", description).strip()

        if "[可选]" in rest or "(可选)" in rest:
            required = False
            description = re.sub(r"[\[\(]?可选[\]\)]?", "", description).strip()

        default_match = re.search(r"默认[：:]\s*(.+?)(?:[,，]|$)", rest)
        if default_match:
            default = default_match.group(1).strip()

        return SkillParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
            default=default,
            enum=enum,
        )

    def _parse_parameter_table_row(self, line: str) -> SkillParameter | None:
        """解析参数表格行"""
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 2:
            return None

        name = cells[0]
        param_type = cells[1] if len(cells) > 1 else "string"
        description = cells[2] if len(cells) > 2 else ""
        required = cells[3].lower() not in ["false", "否", "可选"] if len(cells) > 3 else True

        return SkillParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
        )

    def _parse_examples_section(self, content: str) -> list[SkillExample]:
        """解析示例章节"""
        examples = []
        current_example: dict[str, Any] = {}
        current_key = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("### ") or line.startswith("**示例"):
                if current_example:
                    examples.append(SkillExample(**current_example))
                current_example = {"name": line.replace("#", "").replace("*", "").strip()}
                current_key = None
            elif line.startswith("**输入**") or line.lower().startswith("input:"):
                current_key = "input"
                current_example["input"] = {}
            elif line.startswith("**输出**") or line.lower().startswith("output:"):
                current_key = "output"
            elif current_key == "input" and ":" in line:
                key, value = line.split(":", 1)
                current_example["input"][key.strip()] = value.strip()
            elif current_key == "output":
                if "output" not in current_example:
                    current_example["output"] = ""
                current_example["output"] += line + "\n"

        if current_example:
            examples.append(SkillExample(**current_example))

        return examples

    def _parse_notes_section(self, content: str) -> list[str]:
        """解析注意事项章节"""
        notes = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                notes.append(line[2:])
            elif line.startswith(f"{len(notes) + 1}."):
                notes.append(line.split(".", 1)[1].strip())
        return notes
