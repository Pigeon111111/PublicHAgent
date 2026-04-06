"""技能注册表

管理所有已加载的技能，提供查询和加载接口。
"""

from pathlib import Path
from typing import Any

from backend.tools.skills.loader import SkillLoader, SkillLoaderError
from backend.tools.skills.models import Skill


class SkillRegistry:
    """技能注册表

    管理所有技能的注册、查询和加载。
    """

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        """初始化技能注册表

        Args:
            skills_dir: 技能目录路径
        """
        self._loader = SkillLoader(skills_dir)
        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def load_all(self, force_reload: bool = False) -> list[str]:
        """加载所有技能

        Args:
            force_reload: 是否强制重新加载

        Returns:
            加载的技能名称列表
        """
        if self._loaded and not force_reload:
            return list(self._skills.keys())

        self._skills.clear()
        loaded_names = []

        for skill_name in self._loader.discover_skills():
            try:
                skill = self._loader.load_skill(skill_name)
                self._skills[skill.name] = skill
                loaded_names.append(skill.name)
            except SkillLoaderError:
                loaded_names.append(skill_name)

        self._loaded = True
        return loaded_names

    def get(self, skill_name: str) -> Skill:
        """获取技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill 对象

        Raises:
            KeyError: 技能不存在
        """
        if not self._loaded:
            self.load_all()

        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")

        return self._skills[skill_name]

    def has(self, skill_name: str) -> bool:
        """检查技能是否存在

        Args:
            skill_name: 技能名称

        Returns:
            是否存在
        """
        if not self._loaded:
            self.load_all()
        return skill_name in self._skills

    def list_skills(self) -> list[str]:
        """列出所有技能名称

        Returns:
            技能名称列表
        """
        if not self._loaded:
            self.load_all()
        return list(self._skills.keys())

    def get_all_skills(self) -> list[Skill]:
        """获取所有技能

        Returns:
            Skill 对象列表
        """
        if not self._loaded:
            self.load_all()
        return list(self._skills.values())

    def get_by_category(self, category: str) -> list[Skill]:
        """按类别获取技能

        Args:
            category: 技能类别

        Returns:
            Skill 对象列表
        """
        if not self._loaded:
            self.load_all()

        return [
            skill for skill in self._skills.values()
            if skill.metadata.category == category
        ]

    def get_by_tag(self, tag: str) -> list[Skill]:
        """按标签获取技能

        Args:
            tag: 技能标签

        Returns:
            Skill 对象列表
        """
        if not self._loaded:
            self.load_all()

        return [
            skill for skill in self._skills.values()
            if tag in skill.metadata.tags
        ]

    def search(self, query: str) -> list[Skill]:
        """搜索技能

        Args:
            query: 搜索关键词

        Returns:
            匹配的 Skill 对象列表
        """
        if not self._loaded:
            self.load_all()

        query_lower = query.lower()
        results = []

        for skill in self._skills.values():
            if (
                query_lower in skill.name.lower()
                or query_lower in skill.description.lower()
                or query_lower in skill.metadata.category.lower()
                or any(query_lower in tag.lower() for tag in skill.metadata.tags)
            ):
                results.append(skill)

        return results

    def register_skill(self, skill: Skill) -> None:
        """手动注册技能

        Args:
            skill: Skill 对象

        Raises:
            ValueError: 技能已存在
        """
        if skill.name in self._skills:
            raise ValueError(f"技能已存在: {skill.name}")
        self._skills[skill.name] = skill
        self._loaded = True

    def unregister_skill(self, skill_name: str) -> None:
        """注销技能

        Args:
            skill_name: 技能名称

        Raises:
            KeyError: 技能不存在
        """
        if skill_name not in self._skills:
            raise KeyError(f"技能不存在: {skill_name}")
        del self._skills[skill_name]

    def get_openai_tools_definition(self) -> list[dict[str, Any]]:
        """获取所有技能的 OpenAI 工具定义

        Returns:
            OpenAI 工具定义列表
        """
        if not self._loaded:
            self.load_all()

        return [skill.to_openai_tool_definition() for skill in self._skills.values()]

    def clear(self) -> None:
        """清空所有技能"""
        self._skills.clear()
        self._loaded = False
        self._loader.clear_cache()


_global_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表

    Returns:
        SkillRegistry 实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def reset_skill_registry() -> None:
    """重置全局技能注册表"""
    global _global_registry
    _global_registry = None
