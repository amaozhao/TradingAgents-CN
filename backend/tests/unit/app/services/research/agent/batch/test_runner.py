from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.schemas.analysis import AnalysisParameters
from app.services.research.agent.batch import context as batch_context
from app.services.research.agent.batch.runner import BatchStockWorkflow
from app.services.research.agent.batch.state import BatchWorkflowState
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[BatchWorkflowState] = []
        self.child_updates: list[tuple[str, str, str, str, int, str | None]] = []
        self.aggregate_updates: list[BatchWorkflowState] = []

    async def save_submitted_batch(self, state: BatchWorkflowState) -> None:
        self.saved.append(state)

    async def update_child(self, batch_id, user_id, child) -> bool:
        self.child_updates.append(
            (
                batch_id,
                user_id,
                child.task_id,
                child.status,
                child.progress,
                child.error,
            )
        )
        return True

    async def update_batch_aggregate(self, state: BatchWorkflowState) -> bool:
        self.aggregate_updates.append(state)
        return True


def _tool_context(events: list[dict[str, object]]) -> ToolExecutionContext:
    async def emit(event: dict[str, object]) -> None:
        events.append(event)

    principal = ResearchPrincipal.from_user(
        {"id": "user-1", "username": "alice", "is_admin": False, "roles": []},
        session_id="session-1",
    )
    return ToolExecutionContext(
        principal=principal,
        session_id="session-1",
        request_id="attempt-1",
        event_emitter=emit,
    )


@pytest.fixture(autouse=True)
def analysis_parameters(monkeypatch) -> None:
    def fake_analysis_parameters(payload: dict[str, Any]):
        return (
            AnalysisParameters(
                market_type=payload.get("market_type") or "A股",
                research_depth=payload.get("research_depth") or "标准",
                selected_analysts=payload.get("selected_analysts")
                or ["market", "fundamentals"],
                language=payload.get("language") or "zh-CN",
                quick_analysis_model=payload.get("quick_analysis_model") or "quick",
                deep_analysis_model=payload.get("deep_analysis_model") or "deep",
            ),
            [],
            [],
        )

    monkeypatch.setattr(batch_context, "_analysis_parameters", fake_analysis_parameters)


@pytest.mark.asyncio
async def test_submit_persists_batch_state_and_returns_tool_result() -> None:
    events: list[dict[str, object]] = []
    repo = FakeRepository()
    workflow = BatchStockWorkflow(
        tool_name="batch_stock_analysis",
        repository=repo,
        id_factory=iter(["batch-1", "task-1", "task-2"]).__next__,
        background_scheduler=None,
    )

    result = await workflow.submit(
        _tool_context(events),
        {"title": "批量分析", "symbols": ["600036", "000001"]},
    )

    assert len(repo.saved) == 1
    state = repo.saved[0]
    assert state.batch_id == "batch-1"
    assert state.user_id == "user-1"
    assert [child.task_id for child in state.children] == ["task-1", "task-2"]
    assert [child.symbol for child in state.children] == ["600036", "000001"]
    assert result["tool"] == "batch_stock_analysis"
    assert result["mode"] == "batch"
    assert result["accepted"] is True
    assert result["batch_id"] == "batch-1"
    assert result["task_ids"] == ["task-1", "task-2"]
    assert result["mapping"] == [
        {"symbol": "600036", "stock_code": "600036", "task_id": "task-1"},
        {"symbol": "000001", "stock_code": "000001", "task_id": "task-2"},
    ]
    assert result["links"] == {"batch": "/tasks?batch_id=batch-1"}


@pytest.mark.asyncio
async def test_submit_emits_batch_stage_and_progress_events() -> None:
    events: list[dict[str, object]] = []
    workflow = BatchStockWorkflow(
        tool_name="batch_stock_analysis",
        repository=FakeRepository(),
        id_factory=iter(["batch-1", "task-1"]).__next__,
        background_scheduler=None,
    )

    await workflow.submit(
        _tool_context(events),
        {"title": "批量分析", "symbols": ["600036"]},
    )

    assert [event["event_type"] for event in events] == [
        "batch_analysis.stage",
        "batch_analysis.progress",
    ]
    assert all(event["batch_id"] == "batch-1" for event in events)
    assert all(event["attempt_id"] == "attempt-1" for event in events)


@pytest.mark.asyncio
async def test_submit_returns_config_required_without_persisting_invalid_payload() -> (
    None
):
    repo = FakeRepository()
    workflow = BatchStockWorkflow(
        tool_name="batch_stock_analysis",
        repository=repo,
        id_factory=iter(["batch-1"]).__next__,
        background_scheduler=None,
    )

    result = await workflow.submit(_tool_context([]), {"title": "批量分析"})

    assert repo.saved == []
    assert result["tool"] == "batch_stock_analysis"
    assert result["status"] == "config_required"
    assert result["accepted"] is False
    assert result["missing"] == ["symbols"]


@pytest.mark.asyncio
async def test_run_until_complete_respects_concurrency_and_records_partial_failure() -> (
    None
):
    events: list[dict[str, object]] = []
    repo = FakeRepository()
    running = 0
    max_running = 0

    async def child_runner(context, state, child, request):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.01)
        running -= 1
        if child.symbol == "000001":
            raise RuntimeError("child failed")
        return {
            "status": "completed",
            "analysis_id": f"analysis-{child.task_id}",
            "report_url": f"/reports/view/{child.task_id}",
        }

    workflow = BatchStockWorkflow(
        tool_name="batch_stock_analysis",
        repository=repo,
        id_factory=iter(["batch-1", "task-1", "task-2", "task-3"]).__next__,
        child_runner=child_runner,
        background_scheduler=None,
    )

    result = await workflow.run_until_complete(
        _tool_context(events),
        {
            "title": "批量分析",
            "symbols": ["600036", "000001", "600519"],
            "max_concurrency": 2,
        },
    )

    assert max_running == 2
    assert result["status"] == "partial"
    assert result["completed_tasks"] == 2
    assert result["failed_tasks"] == 1
    assert result["progress"] == 100
    assert result["children"][1]["status"] == "failed"
    assert result["children"][1]["error"] == "child failed"
    assert ("completed", 100, None) in [update[3:] for update in repo.child_updates]
    assert ("failed", 100, "child failed") in [
        update[3:] for update in repo.child_updates
    ]
    assert repo.aggregate_updates[-1].batch_id == "batch-1"
    progress_events = [
        event for event in events if event["event_type"] == "batch_analysis.progress"
    ]
    assert [event["progress"] for event in progress_events][-1] == 100
    assert events[-1]["event_type"] == "batch_analysis.partial"


@pytest.mark.asyncio
async def test_submit_schedules_background_child_workflows() -> None:
    events: list[dict[str, object]] = []
    repo = FakeRepository()
    scheduled: list[Any] = []

    async def child_runner(context, state, child, request):
        return {
            "status": "completed",
            "analysis_id": f"analysis-{child.task_id}",
            "report_url": f"/reports/view/{child.task_id}",
        }

    workflow = BatchStockWorkflow(
        tool_name="batch_stock_analysis",
        repository=repo,
        id_factory=iter(["batch-1", "task-1", "task-2"]).__next__,
        child_runner=child_runner,
        background_scheduler=scheduled.append,
    )

    result = await workflow.submit(
        _tool_context(events),
        {"title": "批量分析", "symbols": ["600036", "000001"]},
    )

    assert result["batch_id"] == "batch-1"
    assert result["status"] == "processing"
    assert len(scheduled) == 1

    await scheduled[0]

    assert [update[3] for update in repo.child_updates] == [
        "processing",
        "completed",
        "processing",
        "completed",
    ]
    assert repo.aggregate_updates[-1].batch_id == "batch-1"
    assert events[-1]["event_type"] == "batch_analysis.completed"
