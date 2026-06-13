from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.direct import DirectToolMixin


class FakeSessionService:
    async def get_session(self, _session_id: str, _user_id: str) -> dict[str, str]:
        return {"session_id": "session-1"}


class DirectHarness(DirectToolMixin):
    emit_terminal_event = True

    def __init__(self, tool_result: dict[str, Any]) -> None:
        self.session_service = FakeSessionService()
        self.tool_result = tool_result
        self.messages: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    async def _run_tool(self, *, tool_call: dict[str, Any], context):
        return self.tool_result

    async def _append_message(self, **kwargs):
        message = {"message_id": f"message-{len(self.messages) + 1}", **kwargs}
        self.messages.append(message)
        return message

    async def _append_event(self, **kwargs) -> None:
        self.events.append(kwargs)


def _principal() -> ResearchPrincipal:
    return ResearchPrincipal.from_user(
        {"id": "user-1", "username": "alice", "is_admin": False, "roles": []},
        session_id="session-1",
    )


@pytest.mark.asyncio
async def test_direct_tool_records_batch_task_ids_and_batch_id() -> None:
    harness = DirectHarness(
        {
            "tool": "batch_stock_analysis",
            "status": "processing",
            "batch_id": "batch-1",
            "task_ids": ["task-1", "task-2"],
            "message": "批量分析任务处理中。",
        }
    )

    result = await harness.run_direct_tool(
        principal=_principal(),
        session_id="session-1",
        user_message="分析这两个股票",
        tool_name="batch_stock_analysis",
        tool_arguments={"symbols": ["600036", "000001"]},
        attempt_id="attempt-1",
    )

    assert result["task_ids"] == ["task-1", "task-2"]
    assert result["batch_id"] == "batch-1"
    assistant = harness.messages[-1]
    assert assistant["metadata"]["task_ids"] == ["task-1", "task-2"]
    assert assistant["metadata"]["batch_id"] == "batch-1"
    assert harness.events[-1]["payload"]["task_ids"] == ["task-1", "task-2"]
    assert harness.events[-1]["payload"]["batch_id"] == "batch-1"


@pytest.mark.asyncio
async def test_direct_batch_tool_message_uses_readable_summary() -> None:
    harness = DirectHarness(
        {
            "tool": "batch_stock_analysis",
            "status": "completed",
            "batch_id": "batch-1",
            "total_tasks": 2,
            "completed_tasks": 2,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "task_ids": ["task-1", "task-2"],
            "children": [
                {"symbol": "000002", "task_id": "task-1", "status": "completed"},
                {"symbol": "000338", "task_id": "task-2", "status": "completed"},
            ],
            "summary": "批量分析状态：2/2 成功，0 失败，0 取消。",
            "message": "批量分析已完成。",
            "links": {"batch": "/tasks?batch_id=batch-1"},
        }
    )

    result = await harness.run_direct_tool(
        principal=_principal(),
        session_id="session-1",
        user_message="分析这两个股票",
        tool_name="batch_stock_analysis",
        tool_arguments={"symbols": ["000002", "000338"]},
        attempt_id="attempt-1",
    )

    assert result["content"] == (
        "批量分析已完成。\n"
        "批量分析状态：2/2 成功，0 失败，0 取消。\n"
        "批次链接：/tasks?batch_id=batch-1"
    )
    assert '"children"' not in result["content"]
    assert harness.messages[-1]["content"] == result["content"]


@pytest.mark.asyncio
async def test_direct_tool_preserves_single_task_and_job_id_metadata() -> None:
    harness = DirectHarness(
        {
            "tool": "stock_analysis",
            "status": "processing",
            "task_id": "task-1",
            "job_id": "job-1",
        }
    )

    result = await harness.run_direct_tool(
        principal=_principal(),
        session_id="session-1",
        user_message="分析股票",
        tool_name="stock_analysis",
        tool_arguments={"symbol": "600036"},
    )

    assert result["task_ids"] == ["task-1", "job-1"]
    assert harness.messages[-1]["metadata"]["task_ids"] == ["task-1", "job-1"]


@pytest.mark.asyncio
async def test_direct_tool_deduplicates_task_ids() -> None:
    harness = DirectHarness(
        {
            "tool": "batch_stock_analysis",
            "status": "processing",
            "task_id": "task-1",
            "job_id": "task-1",
            "task_ids": ["task-1", "task-2"],
        }
    )

    result = await harness.run_direct_tool(
        principal=_principal(),
        session_id="session-1",
        user_message="分析股票",
        tool_name="batch_stock_analysis",
        tool_arguments={"symbols": ["600036", "000001"]},
    )

    assert result["task_ids"] == ["task-1", "task-2"]
