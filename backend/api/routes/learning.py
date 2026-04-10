"""自学习轨迹与 Skill 查询接口。"""

from fastapi import APIRouter, HTTPException, Query

from backend.learning.trajectory import TrajectoryRecorder
from backend.tools.skills.registry import get_skill_registry

router = APIRouter()


@router.get("/learning/trajectories")
async def list_trajectories(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    """列出最近的数据分析学习轨迹。"""
    recorder = TrajectoryRecorder()
    trajectories = recorder.list_recent(limit=limit)
    return {
        "trajectories": [trajectory.model_dump() for trajectory in trajectories],
        "total": len(trajectories),
    }


@router.get("/learning/trajectories/{trajectory_id}")
async def get_trajectory(trajectory_id: str) -> dict[str, object]:
    """读取单条学习轨迹。"""
    recorder = TrajectoryRecorder()
    try:
        trajectory = recorder.load(trajectory_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="学习轨迹不存在") from exc
    return trajectory.model_dump()


@router.get("/learning/skills")
async def list_learned_skills() -> dict[str, object]:
    """列出自动学习生成的 Skill。"""
    registry = get_skill_registry()
    skills = [
        {
            "name": skill.name,
            "description": skill.description,
            "category": skill.metadata.category,
            "tags": skill.metadata.tags,
            "enabled": registry.is_enabled(skill.name),
        }
        for skill in registry.get_all_skills()
        if skill.metadata.category == "learned-analysis"
    ]
    return {"skills": skills, "total": len(skills)}
