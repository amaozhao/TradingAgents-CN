from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from .state import BatchChildState, BatchWorkflowState, aggregate_batch_status

BatchCompletionEventType = Literal[
    "batch_analysis.completed",
    "batch_analysis.partial",
    "batch_analysis.failed",
]

BatchChildEventType = Literal[
    "batch_analysis.child_started",
    "batch_analysis.child_completed",
    "batch_analysis.child_failed",
]


def build_batch_stage_event(
    state: BatchWorkflowState,
    *,
    attempt_id: str | None,
    stage: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        **_base_event(state, attempt_id=attempt_id),
        "event_type": "batch_analysis.stage",
        "stage": stage,
        "status": status,
        "message": message,
    }


def build_batch_child_event(
    state: BatchWorkflowState,
    child: BatchChildState,
    *,
    attempt_id: str | None,
    event_type: BatchChildEventType,
    message: str,
) -> dict[str, Any]:
    return {
        **_base_event(state, attempt_id=attempt_id),
        "event_type": event_type,
        "symbol": child.symbol,
        "stock_code": child.stock_code,
        "task_id": child.task_id,
        "status": child.status,
        "progress": child.progress,
        "analysis_id": child.analysis_id,
        "report_url": child.report_url,
        "error": child.error,
        "message": message,
    }


def build_batch_progress_event(
    state: BatchWorkflowState,
    *,
    attempt_id: str | None,
) -> dict[str, Any]:
    aggregate = aggregate_batch_status(state)
    return {
        **_base_event(state, attempt_id=attempt_id),
        "event_type": "batch_analysis.progress",
        "status": aggregate.status,
        "progress": aggregate.progress,
        "total_tasks": aggregate.total_tasks,
        "completed": aggregate.completed_tasks,
        "failed": aggregate.failed_tasks,
        "cancelled": aggregate.cancelled_tasks,
        "processing": aggregate.processing_tasks,
        "children": [_child_payload(child) for child in state.children],
    }


def build_batch_completion_event(
    state: BatchWorkflowState,
    *,
    attempt_id: str | None,
    event_type: BatchCompletionEventType,
    message: str,
) -> dict[str, Any]:
    aggregate = aggregate_batch_status(state)
    return {
        **_base_event(state, attempt_id=attempt_id),
        "event_type": event_type,
        "status": aggregate.status,
        "progress": aggregate.progress,
        "total_tasks": aggregate.total_tasks,
        "completed": aggregate.completed_tasks,
        "failed": aggregate.failed_tasks,
        "cancelled": aggregate.cancelled_tasks,
        "message": message,
        "children": [_child_payload(child) for child in state.children],
    }


def _base_event(
    state: BatchWorkflowState,
    *,
    attempt_id: str | None,
) -> dict[str, Any]:
    return {
        "tool_name": "batch_stock_analysis",
        "mode": "batch",
        "batch_id": state.batch_id,
        "attempt_id": attempt_id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _child_payload(child: BatchChildState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": child.symbol,
        "stock_code": child.stock_code,
        "task_id": child.task_id,
        "status": child.status,
        "progress": child.progress,
    }
    if child.analysis_id:
        payload["analysis_id"] = child.analysis_id
    if child.report_url:
        payload["report_url"] = child.report_url
    if child.error:
        payload["error"] = child.error
    return payload
