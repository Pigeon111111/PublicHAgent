"""自学习数据分析工作流测试。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.agents.intent.recognizer import IntentRecognizer
from backend.agents.planner.planner_agent import PlannerAgent
from backend.core.workflow import AgentWorkflow
from backend.sandbox.safe_executor import SafeCodeExecutor, SafeExecutionContext
from backend.tools.skills.registry import reset_skill_registry


def test_safe_executor_restricts_paths(tmp_path: Path) -> None:
    """受限执行器应能读取输入文件，并拒绝读取工作区外文件。"""
    input_dir = tmp_path / "input"
    workspace_dir = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    for directory in (input_dir, workspace_dir, output_dir):
        directory.mkdir()

    input_file = input_dir / "data.csv"
    input_file.write_text("age\n28\n35\n", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    executor = SafeCodeExecutor(
        SafeExecutionContext(
            session_id="pytest_safe_executor",
            input_dir=input_dir,
            workspace_dir=workspace_dir,
            output_dir=output_dir,
            input_files=[input_file],
        )
    )

    ok_result = executor.execute(
        """
from pathlib import Path

text = Path(PH_INPUT_FILES[0]).read_text(encoding="utf-8")
(Path(PH_OUTPUT_DIR) / "ok.txt").write_text(text, encoding="utf-8")
print(text)
""",
        timeout=10,
    )
    assert ok_result.success is True
    assert (output_dir / "ok.txt").exists()

    blocked_result = executor.execute(
        f"""
from pathlib import Path

print(Path(r"{outside_file}").read_text(encoding="utf-8"))
""",
        timeout=10,
    )
    assert blocked_result.success is False
    assert "PermissionError" in blocked_result.error


def test_safe_executor_can_interrupt_running_code(tmp_path: Path) -> None:
    """受限执行器应能按中断信号停止长时间运行的脚本。"""
    input_dir = tmp_path / "input"
    workspace_dir = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    for directory in (input_dir, workspace_dir, output_dir):
        directory.mkdir()

    interrupted = {"value": False}
    executor = SafeCodeExecutor(
        SafeExecutionContext(
            session_id="pytest_interrupt_executor",
            input_dir=input_dir,
            workspace_dir=workspace_dir,
            output_dir=output_dir,
            input_files=[],
        ),
        should_cancel=lambda: interrupted["value"],
    )

    interrupted["value"] = True
    result = executor.execute(
        """
import time

while True:
    time.sleep(0.5)
""",
        timeout=10,
    )

    assert result.success is False
    assert "中断" in result.error
    assert result.execution_time < 3


@pytest.mark.asyncio
async def test_workflow_runs_analysis_and_learns_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    """无 LLM 时，工作流也应完成分析并把成功轨迹学习为 Skill。"""
    upload_file = Path("data/uploads/pytest_self_learning.csv")
    session_dir = Path("data/sessions/pytest_self_learning")
    learned_skill: str | None = None
    trajectory_id: str | None = None

    def raise_no_llm(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("测试中禁用 LLM")

    async def raise_no_intent_llm(_self: IntentRecognizer, _query: str) -> object:
        raise RuntimeError("测试中禁用意图 LLM")

    monkeypatch.setattr(PlannerAgent, "_get_llm", raise_no_llm)
    monkeypatch.setattr(IntentRecognizer, "_classify_with_llm", raise_no_intent_llm)

    try:
        upload_file.parent.mkdir(parents=True, exist_ok=True)
        upload_file.write_text("name,age\nalice,28\nbob,35\n", encoding="utf-8")

        workflow = AgentWorkflow(user_id="pytest")
        result = await workflow.run(
            "使用新的年龄结构探索分析方法分析数据",
            thread_id="pytest_self_learning",
            user_context={"file_paths": [str(upload_file.resolve())]},
        )

        learned_skill = result.get("learned_skill")
        trajectory_id = result.get("trajectory_id")
        output_dir = session_dir / "output"

        assert result["final_result"]
        assert learned_skill
        assert trajectory_id
        assert (output_dir / "analysis_report.md").exists()
        assert (output_dir / "analysis_result.json").exists()
        assert Path(f"data/trajectories/{trajectory_id}.json").exists()
        assert Path(f"backend/tools/skills/{learned_skill}/SKILL.md").exists()
    finally:
        if upload_file.exists():
            upload_file.unlink()
        if session_dir.exists():
            shutil.rmtree(session_dir)
        if trajectory_id:
            trajectory_file = Path(f"data/trajectories/{trajectory_id}.json")
            if trajectory_file.exists():
                trajectory_file.unlink()
        if learned_skill:
            skill_dir = Path("backend/tools/skills") / learned_skill
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
        reset_skill_registry()
