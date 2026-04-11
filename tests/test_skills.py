"""技能系统单元测试"""

from pathlib import Path

import pytest

from backend.tools.skills.loader import SkillLoader, SkillLoaderError
from backend.tools.skills.models import (
    Skill,
    SkillExample,
    SkillMetadata,
    SkillParameter,
)
from backend.tools.skills.registry import (
    SkillRegistry,
    get_skill_registry,
    reset_skill_registry,
)


class TestSkillParameter:
    """测试 SkillParameter"""

    def test_default_values(self) -> None:
        """测试默认值"""
        param = SkillParameter(name="test_param")
        assert param.type == "string"
        assert param.description == ""
        assert param.required is True
        assert param.default is None
        assert param.enum is None

    def test_custom_values(self) -> None:
        """测试自定义值"""
        param = SkillParameter(
            name="age",
            type="integer",
            description="年龄",
            required=False,
            default=0,
            enum=None,
        )
        assert param.name == "age"
        assert param.type == "integer"
        assert param.required is False
        assert param.default == 0


class TestSkillMetadata:
    """测试 SkillMetadata"""

    def test_default_values(self) -> None:
        """测试默认值"""
        metadata = SkillMetadata(name="test_skill")
        assert metadata.version == "1.0.0"
        assert metadata.description == ""
        assert metadata.author == ""
        assert metadata.tags == []
        assert metadata.category == "general"

    def test_custom_values(self) -> None:
        """测试自定义值"""
        metadata = SkillMetadata(
            name="regression",
            version="2.0.0",
            description="回归分析",
            author="Test Author",
            tags=["statistics", "regression"],
            category="statistics",
        )
        assert metadata.name == "regression"
        assert metadata.version == "2.0.0"
        assert "statistics" in metadata.tags


class TestSkill:
    """测试 Skill"""

    @pytest.fixture
    def sample_skill(self) -> Skill:
        """创建示例技能"""
        return Skill(
            metadata=SkillMetadata(
                name="test_skill",
                description="测试技能",
                category="test",
            ),
            parameters=[
                SkillParameter(name="param1", type="string", required=True),
                SkillParameter(name="param2", type="integer", required=False, default=0),
            ],
            prompt_template="Hello {name}, your value is {value}",
            examples=[
                SkillExample(name="示例1", input={"name": "test"}, output="result")
            ],
            notes=["注意1", "注意2"],
        )

    def test_name_and_description(self, sample_skill: Skill) -> None:
        """测试名称和描述属性"""
        assert sample_skill.name == "test_skill"
        assert sample_skill.description == "测试技能"

    def test_get_required_parameters(self, sample_skill: Skill) -> None:
        """测试获取必需参数"""
        required = sample_skill.get_required_parameters()
        assert len(required) == 1
        assert required[0].name == "param1"

    def test_get_optional_parameters(self, sample_skill: Skill) -> None:
        """测试获取可选参数"""
        optional = sample_skill.get_optional_parameters()
        assert len(optional) == 1
        assert optional[0].name == "param2"

    def test_render_prompt(self, sample_skill: Skill) -> None:
        """测试渲染提示词"""
        result = sample_skill.render_prompt(name="Alice", value=42)
        assert result == "Hello Alice, your value is 42"

    def test_validate_parameters_success(self, sample_skill: Skill) -> None:
        """测试参数验证成功"""
        is_valid, errors = sample_skill.validate_parameters({"param1": "value"})
        assert is_valid is True
        assert errors == []

    def test_validate_parameters_missing_required(self, sample_skill: Skill) -> None:
        """测试缺少必需参数"""
        is_valid, errors = sample_skill.validate_parameters({})
        assert is_valid is False
        assert "缺少必需参数: param1" in errors

    def test_validate_parameters_unknown_param(self, sample_skill: Skill) -> None:
        """测试未知参数"""
        is_valid, errors = sample_skill.validate_parameters({
            "param1": "value",
            "unknown": "value"
        })
        assert is_valid is False
        assert "未知参数: unknown" in errors

    def test_to_openai_tool_definition(self, sample_skill: Skill) -> None:
        """测试转换为 OpenAI 工具定义"""
        definition = sample_skill.to_openai_tool_definition()
        assert definition["type"] == "function"
        assert definition["function"]["name"] == "test_skill"
        assert "parameters" in definition["function"]
        assert "param1" in definition["function"]["parameters"]["properties"]


class TestSkillLoader:
    """测试 SkillLoader"""

    @pytest.fixture
    def skills_dir(self, tmp_path: Path) -> Path:
        """创建测试技能目录"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()

        skill_content = """---
name: test_skill
version: 1.0.0
description: 测试技能
category: test
---

# 测试技能

## 参数

- `input_data`: (string) 输入数据
- `options`: (object) 配置选项 [可选]

## 提示词模板

请处理以下数据：{input_data}

## 注意事项

- 注意事项1
- 注意事项2
"""
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
        return skills_dir

    def test_discover_skills(self, skills_dir: Path) -> None:
        """测试发现技能"""
        loader = SkillLoader(skills_dir)
        skills = loader.discover_skills()
        assert "test_skill" in skills

    def test_load_skill(self, skills_dir: Path) -> None:
        """测试加载技能"""
        loader = SkillLoader(skills_dir)
        skill = loader.load_skill("test_skill")
        assert skill.name == "test_skill"
        assert skill.description == "测试技能"
        assert skill.metadata.category == "test"

    def test_load_skill_not_found(self, tmp_path: Path) -> None:
        """测试加载不存在的技能"""
        loader = SkillLoader(tmp_path)
        with pytest.raises(SkillLoaderError, match="技能文件不存在"):
            loader.load_skill("nonexistent")

    def test_load_skill_with_cache(self, skills_dir: Path) -> None:
        """测试缓存加载"""
        loader = SkillLoader(skills_dir)
        skill1 = loader.load_skill("test_skill")
        skill2 = loader.load_skill("test_skill")
        assert skill1 is skill2

    def test_load_skill_without_cache(self, skills_dir: Path) -> None:
        """测试不使用缓存"""
        loader = SkillLoader(skills_dir)
        skill1 = loader.load_skill("test_skill", use_cache=False)
        skill2 = loader.load_skill("test_skill", use_cache=False)
        assert skill1 is not skill2

    def test_reload_skill(self, skills_dir: Path) -> None:
        """测试重新加载技能"""
        loader = SkillLoader(skills_dir)
        skill1 = loader.load_skill("test_skill")
        skill2 = loader.reload_skill("test_skill")
        assert skill1 is not skill2

    def test_clear_cache(self, skills_dir: Path) -> None:
        """测试清除缓存"""
        loader = SkillLoader(skills_dir)
        loader.load_skill("test_skill")
        loader.clear_cache()
        assert loader._cache == {}

    def test_load_all_skills(self, skills_dir: Path) -> None:
        """测试加载所有技能"""
        loader = SkillLoader(skills_dir)
        skills = loader.load_all_skills()
        assert len(skills) == 1
        assert skills[0].name == "test_skill"


class TestSkillRegistry:
    """测试 SkillRegistry"""

    @pytest.fixture
    def skills_dir(self, tmp_path: Path) -> Path:
        """创建测试技能目录"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()

        skill_content = """---
name: test_skill
version: 1.0.0
description: 测试技能
category: test
tags:
  - test
---

# 测试技能

## 参数

- `input`: (string) 输入

## 提示词模板

处理 {input}
"""
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
        return skills_dir

    def setup_method(self) -> None:
        """每个测试前重置全局注册表"""
        reset_skill_registry()

    def teardown_method(self) -> None:
        """每个测试后重置全局注册表"""
        reset_skill_registry()

    def test_load_all(self, skills_dir: Path) -> None:
        """测试加载所有技能"""
        registry = SkillRegistry(skills_dir)
        names = registry.load_all()
        assert "test_skill" in names

    def test_get(self, skills_dir: Path) -> None:
        """测试获取技能"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        skill = registry.get("test_skill")
        assert skill.name == "test_skill"

    def test_get_not_found(self, skills_dir: Path) -> None:
        """测试获取不存在的技能"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        with pytest.raises(KeyError, match="技能不存在"):
            registry.get("nonexistent")

    def test_has(self, skills_dir: Path) -> None:
        """测试检查技能是否存在"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        assert registry.has("test_skill") is True
        assert registry.has("nonexistent") is False

    def test_list_skills(self, skills_dir: Path) -> None:
        """测试列出技能"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        skills = registry.list_skills()
        assert "test_skill" in skills

    def test_get_by_category(self, skills_dir: Path) -> None:
        """测试按类别获取"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        skills = registry.get_by_category("test")
        assert len(skills) == 1

    def test_get_by_tag(self, skills_dir: Path) -> None:
        """测试按标签获取"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        skills = registry.get_by_tag("test")
        assert len(skills) == 1

    def test_search(self, skills_dir: Path) -> None:
        """测试搜索"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        results = registry.search("test")
        assert len(results) == 1

    def test_register_skill(self, skills_dir: Path) -> None:
        """测试手动注册"""
        registry = SkillRegistry(skills_dir)
        skill = Skill(
            metadata=SkillMetadata(name="manual_skill"),
            prompt_template="test",
        )
        registry.register_skill(skill)
        assert registry.has("manual_skill")

    def test_register_duplicate(self, skills_dir: Path) -> None:
        """测试注册重复技能"""
        registry = SkillRegistry(skills_dir)
        skill = Skill(
            metadata=SkillMetadata(name="test"),
            prompt_template="test",
        )
        registry.register_skill(skill)
        with pytest.raises(ValueError, match="技能已存在"):
            registry.register_skill(skill)

    def test_unregister_skill(self, skills_dir: Path) -> None:
        """测试注销技能"""
        registry = SkillRegistry(skills_dir)
        skill = Skill(
            metadata=SkillMetadata(name="to_remove"),
            prompt_template="test",
        )
        registry.register_skill(skill)
        registry.unregister_skill("to_remove")
        assert not registry.has("to_remove")

    def test_get_openai_tools_definition(self, skills_dir: Path) -> None:
        """测试获取 OpenAI 工具定义"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        definitions = registry.get_openai_tools_definition()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "test_skill"

    def test_clear(self, skills_dir: Path) -> None:
        """测试清空"""
        registry = SkillRegistry(skills_dir)
        registry.load_all()
        registry.clear()
        assert registry._skills == {}
        assert registry._loaded is False


class TestGlobalSkillRegistry:
    """测试全局技能注册表"""

    def setup_method(self) -> None:
        """每个测试前重置"""
        reset_skill_registry()

    def teardown_method(self) -> None:
        """每个测试后重置"""
        reset_skill_registry()

    def test_get_skill_registry(self) -> None:
        """测试获取全局注册表"""
        registry1 = get_skill_registry()
        registry2 = get_skill_registry()
        assert registry1 is registry2

    def test_reset_skill_registry(self) -> None:
        """测试重置全局注册表"""
        registry1 = get_skill_registry()
        reset_skill_registry()
        registry2 = get_skill_registry()
        assert registry1 is not registry2


class TestSkillLoaderIntegration:
    """测试技能加载器集成"""

    def test_load_real_skills(self) -> None:
        """测试加载实际技能文件"""
        skills_dir = Path(__file__).parent.parent / "backend" / "tools" / "skills"
        if not skills_dir.exists():
            pytest.skip("技能目录不存在")

        loader = SkillLoader(skills_dir)
        discovered = loader.discover_skills()

        assert len(discovered) >= 4
        assert "descriptive_statistics" in discovered
        assert "regression_analysis" in discovered
        assert "survival_analysis" in discovered
        assert "data_visualization" in discovered

        for skill_name in discovered:
            skill = loader.load_skill(skill_name)
            assert skill.name
            assert skill.description
            assert skill.metadata.category


class TestHierarchicalSkillMetadata:
    """测试方法家族与细分变体元数据。"""

    def test_metadata_hierarchy_defaults(self) -> None:
        metadata = SkillMetadata(
            name="hierarchical_skill",
            category="learned-analysis",
            method_family="regression_analysis",
            method_variant="logistic_regression",
            process_signature="sig123",
            input_schema_signature="schema123",
            lifecycle_state="candidate",
            confidence_score=0.82,
        )
        assert metadata.normalized_method_family == "regression_analysis"
        assert metadata.method_variant == "logistic_regression"
        assert metadata.lifecycle_state == "candidate"
        assert metadata.is_learned is True

    def test_loader_parses_hierarchical_front_matter(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "hierarchical_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: hierarchical_skill
version: 1.0.0
description: 分层技能
category: learned-analysis
analysis_domain: public_health
method_family: survival_analysis
method_variant: cox_ph
process_signature: proc_sig
input_schema_signature: input_sig
verifier_family: survival_analysis
confidence_score: 0.93
lifecycle_state: active
usage_count: 5
verifier_pass_rate: 0.8
---

# hierarchical_skill

## 能力描述

**能力范围**：执行 Cox 生存分析
""",
            encoding="utf-8",
        )
        skill = SkillLoader(skills_dir).load_skill("hierarchical_skill", use_cache=False)
        assert skill.metadata.analysis_domain == "public_health"
        assert skill.metadata.method_family == "survival_analysis"
        assert skill.metadata.method_variant == "cox_ph"
        assert skill.metadata.lifecycle_state == "active"

    def test_registry_family_and_variant_queries(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "variant_a"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            """---
name: variant_a
version: 1.0.0
description: 回归变体 A
category: learned-analysis
method_family: regression_analysis
method_variant: linear_regression
lifecycle_state: active
confidence_score: 0.8
usage_count: 3
verifier_pass_rate: 0.9
---

# variant_a
## 能力描述
**能力范围**：执行线性回归
""",
            encoding="utf-8",
        )
        registry = SkillRegistry(skills_dir)
        registry.load_all(force_reload=True)
        family_skills = registry.get_by_method_family("regression_analysis")
        assert len(family_skills) == 1
        summary = registry.summarize_method_families()
        assert any(item["family"] == "regression_analysis" for item in summary)
        variants = registry.list_method_variants("regression_analysis")
        assert variants[0]["method_variant"] == "linear_regression"
