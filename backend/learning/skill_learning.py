"""从成功分析轨迹生成可复用 Skill。"""

import hashlib
import re
from pathlib import Path

from backend.learning.trajectory import AnalysisTrajectory
from backend.tools.skills.loader import SkillLoader
from backend.tools.skills.registry import get_skill_registry


class SkillLearningService:
    """Skill 学习服务。"""

    def __init__(self, skills_dir: str | Path | None = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else Path("backend/tools/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def learn_from_trajectory(self, trajectory: AnalysisTrajectory) -> str | None:
        """从成功轨迹生成或更新 Skill。"""
        if not trajectory.success:
            return None

        skill_name = self._choose_skill_name(trajectory.user_query)
        skill_dir = self.skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_file = skill_dir / "SKILL.md"
        content = self._build_skill_markdown(skill_name, trajectory)
        self._security_check(content)
        skill_file.write_text(content, encoding="utf-8")

        loader = SkillLoader(self.skills_dir)
        registry = get_skill_registry()
        loaded_skill = loader.load_skill(skill_name, use_cache=False)
        if registry.has(loaded_skill.name):
            registry.unregister_skill(loaded_skill.name)
        registry.register_skill(loaded_skill)
        registry.enable(loaded_skill.name)

        return loaded_skill.name

    def find_reusable_skill(self, query: str) -> str | None:
        """按查询文本查找已学习 Skill。"""
        registry = get_skill_registry()
        query_terms = set(self._tokenize(query))
        if not query_terms:
            return None

        for skill in registry.get_all_skills():
            if skill.metadata.category != "learned-analysis":
                continue
            haystack = " ".join([
                skill.name,
                skill.description,
                skill.capability.capability,
                " ".join(skill.metadata.tags),
            ])
            skill_terms = set(self._tokenize(haystack))
            if query_terms & skill_terms:
                return skill.name
        return None

    def _choose_skill_name(self, query: str) -> str:
        """生成稳定 Skill 名称。"""
        slug = self._slugify(query)
        digest = hashlib.sha1(query.encode("utf-8", errors="ignore")).hexdigest()[:8]
        if not slug:
            slug = "analysis_method"
        return f"learned_{slug[:40]}_{digest}"

    def _build_skill_markdown(self, skill_name: str, trajectory: AnalysisTrajectory) -> str:
        """生成 SKILL.md 内容。"""
        method = trajectory.user_query.strip().replace("\n", " ")
        data_files = "\n".join(f"- `{Path(path).name}`" for path in trajectory.data_files) or "- 无"
        successful_attempts = [attempt for attempt in trajectory.attempts if attempt.success]
        last_attempt = successful_attempts[-1] if successful_attempts else trajectory.attempts[-1]
        output_files = last_attempt.artifacts.get("output_files", [])
        output_lines = "\n".join(f"- `{Path(str(path)).name}`" for path in output_files) or "- `analysis_report.md`\n- `analysis_result.json`"

        code_template = last_attempt.code.strip()
        if len(code_template) > 8000:
            code_template = code_template[:8000] + "\n# 代码过长，已截断，请参考对应轨迹文件。"

        return f"""---
name: {skill_name}
version: 1.0.0
description: 从成功分析轨迹学习得到的分析方法：{method}
author: PubHAgent
tags:
  - learned
  - data-analysis
category: learned-analysis
min_python_version: "3.10"
dependencies:
  - pandas
  - numpy
  - scipy
---

# {skill_name}

## 能力描述

**能力范围**：复用以下成功分析方法：{method}

**限制条件**：
- 仅适用于结构化表格数据。
- 默认读取会话输入目录中的 CSV、Excel 或 JSON 文件。
- 统计结论需要结合数据质量和领域背景复核。

**适用场景**：
- 用户提出与“{method}”相似的数据分析需求。
- 数据文件字段结构与历史成功轨迹接近。
- 需要快速复用已验证的数据读取、统计摘要和报告输出流程。

## 参数

- `input_files`: (array) 会话输入文件列表
- `output_dir`: (string) 分析结果输出目录
- `analysis_goal`: (string) 用户分析目标

## 提示词模板

你正在复用 PubHAgent 已学习的数据分析 Skill。

历史成功任务：{method}

输入数据示例：
{data_files}

执行要求：
1. 优先复用本 Skill 的代码模板和验证规则。
2. 只能读取会话输入目录中的数据文件。
3. 只能向会话输出目录写入结果。
4. 输出 `analysis_report.md` 和 `analysis_result.json`。
5. 如果字段不匹配，应先解释缺失字段并执行可行的降级分析。

## 成功路径

- 读取结构化数据文件。
- 生成数据规模、字段、缺失值、描述性统计和相关性结果。
- 将结构化结果写入 JSON。
- 将可读报告写入 Markdown。
- 检查输出文件存在且非空。

## 验证规则

- 输出目录存在 `analysis_report.md`。
- 输出目录存在 `analysis_result.json`。
- 报告包含数据规模、字段和主要统计结果。
- 执行过程不访问会话目录之外的路径。

## 失败排查

- 如果没有输入文件，提示用户先上传 CSV、Excel 或 JSON。
- 如果缺少数值列，输出字段结构和缺失值摘要。
- 如果字段名不匹配，先列出实际字段，再执行可行的通用分析。
- 如果依赖库不可用，降级为 pandas/numpy/scipy 能完成的分析。

## 代码模板

```python
{code_template}
```

## 输出产物

{output_lines}

## 注意事项

- 本 Skill 来自轨迹 `{trajectory.trajectory_id}`。
- 自动学习的 Skill 必须在后续任务中持续验证，失败样本可用于更新本 Skill。
"""

    def _security_check(self, content: str) -> None:
        """检查自动生成 Skill 的基本安全性。"""
        blocked_patterns = [
            r"api[_-]?key\s*=",
            r"password\s*=",
            r"token\s*=",
            r"subprocess\.",
            r"import\s+os\b",
            r"shutil\.rmtree",
        ]
        for pattern in blocked_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                raise ValueError(f"自动生成 Skill 未通过安全检查: {pattern}")

    def _slugify(self, text: str) -> str:
        """生成文件安全的 slug。"""
        words = self._tokenize(text)
        if not words:
            digest = str(abs(hash(text)))
            return f"method_{digest[:8]}"
        return "_".join(words[:8])

    def _tokenize(self, text: str) -> list[str]:
        """提取可匹配关键词。"""
        normalized = text.lower()
        ascii_words = re.findall(r"[a-z0-9]+", normalized)
        chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
        words = ascii_words + chinese_chunks
        stop_words = {"the", "and", "for", "with", "data", "analysis", "分析", "数据"}
        return [word for word in words if word not in stop_words]
