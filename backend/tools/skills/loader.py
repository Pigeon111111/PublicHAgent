"""Skill 加载器。

从文件系统动态发现和加载 Skill，支持 YAML front matter 与 Markdown 章节解析。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from backend.tools.skills.models import (
    Skill,
    SkillCapability,
    SkillExample,
    SkillLifecycleState,
    SkillMetadata,
    SkillParameter,
)


class SkillLoaderError(Exception):
    """Skill 加载错误。"""


class SkillLoader:
    """Skill 动态加载器。"""

    SKILL_FILE_NAME = "SKILL.md"

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self._skills_dir = Path(skills_dir) if skills_dir else Path(__file__).parent
        self._cache: dict[str, Skill] = {}

    def discover_skills(self) -> list[str]:
        """发现所有 Skill 目录。"""

        if not self._skills_dir.exists():
            return []

        names: list[str] = []
        for item in self._skills_dir.iterdir():
            if item.is_dir() and (item / self.SKILL_FILE_NAME).exists():
                names.append(item.name)
        return sorted(names)

    def load_skill(self, skill_name: str, use_cache: bool = True) -> Skill:
        """加载单个 Skill。"""

        if use_cache and skill_name in self._cache:
            return self._cache[skill_name]

        skill_dir = self._skills_dir / skill_name
        skill_file = skill_dir / self.SKILL_FILE_NAME
        if not skill_file.exists():
            raise SkillLoaderError(f"技能文件不存在: {skill_file}")

        try:
            skill = self._parse_skill_file(skill_file)
        except Exception as exc:  # noqa: BLE001
            raise SkillLoaderError(f"解析 Skill 失败: {skill_file} - {exc}") from exc

        skill.source_path = str(skill_dir)
        self._cache[skill_name] = skill
        return skill

    def load_all_skills(self, use_cache: bool = True) -> list[Skill]:
        """加载全部 Skill。"""

        skills: list[Skill] = []
        for skill_name in self.discover_skills():
            try:
                skills.append(self.load_skill(skill_name, use_cache=use_cache))
            except SkillLoaderError:
                continue
        return skills

    def reload_skill(self, skill_name: str) -> Skill:
        """重新加载单个 Skill。"""

        self._cache.pop(skill_name, None)
        return self.load_skill(skill_name, use_cache=False)

    def clear_cache(self) -> None:
        """清空缓存。"""

        self._cache.clear()

    def _parse_skill_file(self, skill_file: Path) -> Skill:
        content = skill_file.read_text(encoding="utf-8")
        return self._parse_skill_content(content)

    def _parse_skill_content(self, content: str) -> Skill:
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
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return SkillMetadata(name="unknown"), content

        yaml_content = match.group(1)
        remaining = match.group(2)
        try:
            data = yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError:
            return SkillMetadata(name="unknown"), remaining

        family_default = self._infer_method_family(data)
        metadata = SkillMetadata(
            name=str(data.get("name", "unknown")),
            version=str(data.get("version", "1.0.0")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            tags=list(data.get("tags", []) or []),
            category=str(data.get("category", "general")),
            min_python_version=str(data.get("min_python_version", "3.10")),
            dependencies=list(data.get("dependencies", []) or []),
            analysis_domain=str(data.get("analysis_domain", "general")),
            method_family=str(data.get("method_family", family_default)),
            method_variant=str(data.get("method_variant", "")),
            process_signature=str(data.get("process_signature", "")),
            input_schema_signature=str(data.get("input_schema_signature", "")),
            verifier_family=str(data.get("verifier_family", "")),
            provenance_trajectory_id=str(data.get("provenance_trajectory_id", "")),
            confidence_score=float(data.get("confidence_score", 0.0) or 0.0),
            lifecycle_state=self._normalize_lifecycle_state(data.get("lifecycle_state", "active")),
            last_used_at=str(data.get("last_used_at", "")),
            usage_count=int(data.get("usage_count", 0) or 0),
            verifier_pass_rate=float(data.get("verifier_pass_rate", 0.0) or 0.0),
        )
        return metadata, remaining

    def _normalize_lifecycle_state(self, value: Any) -> SkillLifecycleState:
        lifecycle = str(value or "active").strip()
        if lifecycle == "candidate":
            return "candidate"
        if lifecycle == "deprecated":
            return "deprecated"
        if lifecycle == "legacy":
            return "legacy"
        return "active"

    def _infer_method_family(self, data: dict[str, Any]) -> str:
        """为旧 front matter 推断方法家族。"""

        name = str(data.get("name", "")).strip()
        if name in {"regression_analysis", "survival_analysis"}:
            return name
        if name in {"descriptive_statistics", "descriptive_analysis"}:
            return "descriptive_analysis"
        category = str(data.get("category", "general")).strip()
        return category if category in {"visualization", "general"} else "general"

    def _parse_markdown_sections(self, content: str) -> dict[str, str]:
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_lines: list[str] = []

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

        for line in content.splitlines():
            header_match = re.match(r"^#+\s+(.+)$", line)
            if header_match:
                if current_section is not None:
                    sections[current_section] = "\n".join(current_lines).strip()
                header = header_match.group(1).strip().lower()
                current_section = section_mapping.get(header)
                current_lines = []
                continue

            if current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def _parse_capability_section(self, content: str) -> SkillCapability:
        capability_text = ""
        limitations: list[str] = []
        applicable_scenarios: list[str] = []
        current_mode: str | None = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("**能力范围**") or line.startswith("能力范围"):
                current_mode = "capability"
                capability_text = line.split(":", 1)[-1].split("：", 1)[-1].strip()
                continue
            if line.startswith("**限制条件**") or line.startswith("限制条件"):
                current_mode = "limitations"
                continue
            if line.startswith("**适用场景**") or line.startswith("适用场景"):
                current_mode = "scenarios"
                continue

            if current_mode == "capability" and not capability_text:
                capability_text = line
            elif current_mode == "limitations" and (line.startswith("- ") or line.startswith("* ")):
                limitations.append(line[2:].strip())
            elif current_mode == "scenarios" and (line.startswith("- ") or line.startswith("* ")):
                applicable_scenarios.append(line[2:].strip())

        return SkillCapability(
            capability=capability_text,
            limitations=limitations,
            applicable_scenarios=applicable_scenarios,
        )

    def _parse_parameters_section(self, content: str) -> list[SkillParameter]:
        parameters: list[SkillParameter] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- ") or line.startswith("* "):
                parameter = self._parse_parameter_line(line[2:].strip())
                if parameter is not None:
                    parameters.append(parameter)
                continue
            if line.startswith("|"):
                parameter = self._parse_parameter_table_row(line)
                if parameter is not None:
                    parameters.append(parameter)
        return parameters

    def _parse_parameter_line(self, line: str) -> SkillParameter | None:
        match = re.match(r"`?([\w-]+)`?\s*[:：]\s*(.+)$", line)
        if not match:
            return None

        name = match.group(1).strip()
        rest = match.group(2).strip()
        parameter_type = "string"
        description = rest
        required = True
        default: Any = None

        type_match = re.search(r"\(([^)]+)\)", rest)
        if type_match:
            parameter_type = type_match.group(1).strip()
            description = re.sub(r"\([^)]+\)", "", description, count=1).strip()

        if "可选" in rest:
            required = False
            description = description.replace("[可选]", "").replace("可选", "").strip()

        default_match = re.search(r"默认[:：]\s*([^,，]+)", rest)
        if default_match:
            default = default_match.group(1).strip()

        return SkillParameter(
            name=name,
            type=parameter_type,
            description=description,
            required=required,
            default=default,
        )

    def _parse_parameter_table_row(self, line: str) -> SkillParameter | None:
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        if len(cells) < 2:
            return None
        return SkillParameter(
            name=cells[0],
            type=cells[1] if len(cells) > 1 else "string",
            description=cells[2] if len(cells) > 2 else "",
            required=(cells[3].lower() not in {"false", "否", "可选"}) if len(cells) > 3 else True,
        )

    def _parse_examples_section(self, content: str) -> list[SkillExample]:
        examples: list[SkillExample] = []
        current_example: dict[str, Any] = {}
        current_key: str | None = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("### ") or line.startswith("**示例"):
                if current_example:
                    examples.append(SkillExample(**current_example))
                current_example = {"name": line.replace("#", "").replace("*", "").strip()}
                current_key = None
                continue

            if line.startswith("**输入**") or line.lower().startswith("input:"):
                current_key = "input"
                current_example["input"] = {}
                continue
            if line.startswith("**输出**") or line.lower().startswith("output:"):
                current_key = "output"
                current_example["output"] = ""
                continue

            if current_key == "input" and ":" in line:
                key, value = line.split(":", 1)
                current_example.setdefault("input", {})[key.strip("- ").strip()] = value.strip()
            elif current_key == "output":
                current_example["output"] = f"{current_example.get('output', '')}{line}\n"

        if current_example:
            examples.append(SkillExample(**current_example))

        return examples

    def _parse_notes_section(self, content: str) -> list[str]:
        notes: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("- ") or line.startswith("* "):
                notes.append(line[2:].strip())
            elif re.match(r"^\d+\.\s+", line):
                notes.append(re.sub(r"^\d+\.\s+", "", line))
        return notes
