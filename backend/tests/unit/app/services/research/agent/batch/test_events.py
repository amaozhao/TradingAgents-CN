from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import emitter as emitter_module
from app.services.research.agent.batch.events import (
    build_batch_child_event,
    build_batch_completion_event,
    build_batch_progress_event,
    build_batch_stage_event,
)
from app.services.research.agent.batch.state import BatchChildState, BatchWorkflowState
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.stock import (
    _emit_stock_workflow_stage,
    _stock_workflow_node_emitter,
)
from app.routers.sse import _batch_progress_from_repository_document


def _state() -> BatchWorkflowState:
    return BatchWorkflowState(
        batch_id="batch-1",
        user_id="user-1",
        title="批量分析",
        description=None,
        status="processing",
        parameters={"market_type": "A股"},
        children=[
            BatchChildState(
                symbol="600036",
                stock_code="600036",
                task_id="task-1",
                status="completed",
                progress=100,
            ),
            BatchChildState(
                symbol="000001",
                stock_code="000001",
                task_id="task-2",
                status="processing",
                progress=20,
            ),
        ],
    )


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


def _capturing_context(events: list[dict[str, object]]) -> ToolExecutionContext:
    def emit(event: dict[str, object]):
        events.append(event)

        async def done() -> None:
            return None

        return done()

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


def test_batch_events_include_attempt_id_and_batch_id() -> None:
    state = _state()
    child = state.children[0]

    events = [
        build_batch_stage_event(
            state,
            attempt_id="attempt-1",
            stage="batch_prepare",
            status="completed",
            message="批量状态已准备。",
        ),
        build_batch_child_event(
            state,
            child,
            attempt_id="attempt-1",
            event_type="batch_analysis.child_started",
            message="开始分析 600036。",
        ),
        build_batch_child_event(
            state,
            child,
            attempt_id="attempt-1",
            event_type="batch_analysis.child_completed",
            message="完成分析 600036。",
        ),
        build_batch_child_event(
            state,
            child,
            attempt_id="attempt-1",
            event_type="batch_analysis.child_failed",
            message="分析失败 600036。",
        ),
        build_batch_progress_event(state, attempt_id="attempt-1"),
        build_batch_completion_event(
            state,
            attempt_id="attempt-1",
            event_type="batch_analysis.completed",
            message="批量分析完成。",
        ),
        build_batch_completion_event(
            state,
            attempt_id="attempt-1",
            event_type="batch_analysis.partial",
            message="批量分析部分完成。",
        ),
        build_batch_completion_event(
            state,
            attempt_id="attempt-1",
            event_type="batch_analysis.failed",
            message="批量分析失败。",
        ),
    ]

    assert [event["event_type"] for event in events] == [
        "batch_analysis.stage",
        "batch_analysis.child_started",
        "batch_analysis.child_completed",
        "batch_analysis.child_failed",
        "batch_analysis.progress",
        "batch_analysis.completed",
        "batch_analysis.partial",
        "batch_analysis.failed",
    ]
    for event in events:
        assert event["attempt_id"] == "attempt-1"
        assert event["batch_id"] == "batch-1"


def test_batch_progress_event_contains_legacy_task_page_payload() -> None:
    event = build_batch_progress_event(_state(), attempt_id="attempt-1")

    assert event["status"] == "processing"
    assert event["progress"] == 50
    assert event["total_tasks"] == 2
    assert event["completed"] == 1
    assert event["failed"] == 0
    assert event["processing"] == 1
    assert event["children"] == [
        {
            "symbol": "600036",
            "stock_code": "600036",
            "task_id": "task-1",
            "status": "completed",
            "progress": 100,
        },
        {
            "symbol": "000001",
            "stock_code": "000001",
            "task_id": "task-2",
            "status": "processing",
            "progress": 20,
        },
    ]


def test_sse_repository_progress_preserves_legacy_batch_protocol() -> None:
    progress = _batch_progress_from_repository_document(
        {
            "batch_id": "batch-1",
            "status": "partial_success",
            "tasks": [
                {"task_id": "task-1", "status": "completed"},
                {"task_id": "task-2", "status": "failed"},
                {"task_id": "task-3", "status": "processing"},
            ],
        }
    )

    assert progress["batch_id"] == "batch-1"
    assert progress["status"] == "processing"
    assert progress["progress"] == 66.7
    assert progress["total_tasks"] == 3
    assert progress["completed"] == 1
    assert progress["failed"] == 1
    assert progress["processing"] == 1


def test_sse_repository_progress_keeps_partial_terminal_status() -> None:
    progress = _batch_progress_from_repository_document(
        {
            "batch_id": "batch-1",
            "status": "partial_success",
            "tasks": [
                {"task_id": "task-1", "status": "completed"},
                {"task_id": "task-2", "status": "failed"},
            ],
        }
    )

    assert progress["status"] == "partial"
    assert progress["progress"] == 100.0


@pytest.mark.asyncio
async def test_stock_stage_event_adds_batch_id_only_when_provided() -> None:
    events: list[dict[str, object]] = []
    context = _tool_context(events)

    await _emit_stock_workflow_stage(
        context=context,
        task_id="task-1",
        stage="validate_input",
        status="completed",
        progress=8,
        message="ok",
    )
    await _emit_stock_workflow_stage(
        context=context,
        task_id="task-2",
        stage="validate_input",
        status="completed",
        progress=8,
        message="ok",
        batch_id="batch-1",
    )

    assert "batch_id" not in events[0]
    assert events[1]["batch_id"] == "batch-1"


@pytest.mark.asyncio
async def test_stock_node_event_adds_batch_id_only_when_provided(monkeypatch) -> None:
    events: list[dict[str, object]] = []
    context = _capturing_context(events)

    class FakeFuture:
        def result(self, timeout: int) -> None:
            assert timeout == 5

    def fake_run_coroutine_threadsafe(coro: Any, _loop: Any) -> FakeFuture:
        coro.close()
        return FakeFuture()

    monkeypatch.setattr(
        emitter_module,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    single_emit = _stock_workflow_node_emitter(context=context, task_id="task-1")
    batch_emit = _stock_workflow_node_emitter(
        context=context,
        task_id="task-2",
        batch_id="batch-1",
    )

    assert single_emit is not None
    assert batch_emit is not None
    single_emit("Market Analyst", None)
    batch_emit("Market Analyst", "START")

    assert "batch_id" not in events[0]
    assert events[1]["batch_id"] == "batch-1"
