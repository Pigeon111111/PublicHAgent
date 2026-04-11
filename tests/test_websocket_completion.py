"""WebSocket 完成消息测试。"""

import asyncio

from backend.api.routes.history import reset_history_storage
from backend.api.websocket import SessionContext, _emit_completed_messages
from backend.storage.history_storage import get_history_storage


def test_emit_completed_messages_contains_evaluation_summary() -> None:
    """完成消息应携带 evaluation_report、analysis_id 和轨迹信息。"""
    reset_history_storage()
    storage = get_history_storage()
    record = storage.create_analysis_record(
        query="测试",
        intent="regression_analysis",
        status="processing",
        result_summary="处理中",
        steps_count=1,
        session_id="ws_completion_session",
        task_family="regression_analysis",
    )

    context = SessionContext("ws_completion_session", "default")
    context.current_analysis_id = record["id"]
    result = {
        "intent": "regression_analysis",
        "final_result": "完成",
        "task_family": "regression_analysis",
        "trajectory_id": "traj_ws_001",
        "selected_skill": "learned_variant",
        "evaluation_score": 0.92,
        "evaluation_report": {
            "task_family": "regression_analysis",
            "passed": True,
            "final_score": 0.92,
            "summary": "评估通过",
            "hard_failures": [],
        },
        "execution_results": [],
    }

    async def collect() -> list[object]:
        return [message async for message in _emit_completed_messages(context, session_id="ws_completion_session", result=result)]

    messages = asyncio.run(collect())
    agent_message = next(message for message in messages if getattr(message, "type", "") == "agent")

    assert agent_message.analysis_id == record["id"]
    assert agent_message.trajectory_id == "traj_ws_001"
    assert agent_message.evaluation_report["task_family"] == "regression_analysis"
    assert agent_message.evaluation_score == 0.92
