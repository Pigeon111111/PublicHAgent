"""任务规格注册与加载。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.evaluation.schemas import TaskSpec

TASK_SPEC_DIR = Path(__file__).resolve().parent / "task_specs"


@lru_cache(maxsize=1)
def load_task_specs() -> dict[str, TaskSpec]:
    """加载任务规格。"""
    specs: dict[str, TaskSpec] = {}
    if not TASK_SPEC_DIR.exists():
        return specs

    for path in TASK_SPEC_DIR.glob("*.json"):
        spec = TaskSpec.model_validate_json(path.read_text(encoding="utf-8"))
        specs[spec.family] = spec

    return specs


def resolve_task_spec(intent: str) -> TaskSpec:
    """根据意图匹配任务规格。"""
    normalized_intent = (intent or "").strip()
    for spec in load_task_specs().values():
        if normalized_intent in spec.intents:
            return spec
    return TaskSpec(family=normalized_intent or "general", intents=[normalized_intent])


def list_task_spec_payloads() -> list[dict[str, object]]:
    """便于调试查看当前任务规格。"""
    payloads: list[dict[str, object]] = []
    for spec in load_task_specs().values():
        payloads.append(json.loads(spec.model_dump_json()))
    return payloads
