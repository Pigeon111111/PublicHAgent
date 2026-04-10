"""数据分析轨迹记录。"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AttemptRecord(BaseModel):
    """单次执行尝试记录。"""

    step_id: str
    description: str
    success: bool
    code: str = ""
    output: str = ""
    error: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)


class ValidationRecord(BaseModel):
    """结果验证记录。"""

    passed: bool
    checks: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class AnalysisTrajectory(BaseModel):
    """一次分析任务的完整轨迹。"""

    trajectory_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str = "default"
    session_id: str = "default"
    user_query: str
    intent: str = ""
    data_files: list[str] = Field(default_factory=list)
    plan_summary: str = ""
    attempts: list[AttemptRecord] = Field(default_factory=list)
    validation: ValidationRecord = Field(default_factory=lambda: ValidationRecord(passed=False))
    learned_skill: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        """更新时间戳。"""
        self.updated_at = datetime.now().isoformat()

    @property
    def success(self) -> bool:
        """是否整体成功。"""
        return bool(self.attempts) and all(attempt.success for attempt in self.attempts) and self.validation.passed


class TrajectoryRecorder:
    """轨迹持久化管理器。"""

    def __init__(self, root_dir: str | Path = "data/trajectories") -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save(self, trajectory: AnalysisTrajectory) -> Path:
        """保存轨迹到 JSON 文件。"""
        trajectory.touch()
        path = self.root_dir / f"{trajectory.trajectory_id}.json"
        path.write_text(
            json.dumps(trajectory.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, trajectory_id: str) -> AnalysisTrajectory:
        """读取轨迹。"""
        path = self.root_dir / f"{trajectory_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisTrajectory.model_validate(data)

    def list_recent(self, limit: int = 20) -> list[AnalysisTrajectory]:
        """列出最近轨迹。"""
        files = sorted(
            self.root_dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        trajectories = []
        for path in files[:limit]:
            try:
                trajectories.append(AnalysisTrajectory.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return trajectories
