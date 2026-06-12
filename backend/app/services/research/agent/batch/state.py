from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

BatchStatus = Literal[
    "pending",
    "processing",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "config_required",
]
ChildStatus = Literal[
    "pending",
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
]


@dataclass
class BatchChildState:
    symbol: str
    stock_code: str
    task_id: str
    status: ChildStatus = "pending"
    progress: int = 0
    analysis_id: str | None = None
    report_url: str | None = None
    error: str | None = None


@dataclass
class BatchWorkflowState:
    batch_id: str
    user_id: str
    title: str
    description: str | None
    status: BatchStatus
    parameters: dict[str, Any]
    children: list[BatchChildState] = field(default_factory=list)
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class BatchAggregate:
    status: BatchStatus
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    processing_tasks: int
    progress: int


def aggregate_batch_status(state: BatchWorkflowState) -> BatchAggregate:
    total = len(state.children)
    completed = _count_children(state, "completed")
    failed = _count_children(state, "failed")
    cancelled = _count_children(state, "cancelled")
    processing = _count_children(state, "processing")
    finished = completed + failed + cancelled
    progress = int((finished / total) * 100) if total else 0

    if total == 0:
        status: BatchStatus = state.status
    elif completed == total:
        status = "completed"
    elif failed == total:
        status = "failed"
    elif cancelled == total:
        status = "cancelled"
    elif finished == total and completed > 0 and failed > 0:
        status = "partial"
    elif finished == total and completed > 0 and cancelled > 0:
        status = "partial"
    elif finished == total and failed > 0 and cancelled > 0:
        status = "failed"
    else:
        status = "processing"

    return BatchAggregate(
        status=status,
        total_tasks=total,
        completed_tasks=completed,
        failed_tasks=failed,
        cancelled_tasks=cancelled,
        processing_tasks=processing,
        progress=progress,
    )


def normalize_batch_status_for_document(status: BatchStatus) -> str:
    if status == "partial":
        return "partial_success"
    return status


def build_batch_tool_result(state: BatchWorkflowState) -> dict[str, Any]:
    aggregate = aggregate_batch_status(state)
    task_ids = [child.task_id for child in state.children]
    return {
        "tool": "batch_stock_analysis",
        "mode": "batch",
        "accepted": aggregate.status != "config_required",
        "status": aggregate.status,
        "batch_id": state.batch_id,
        "total_tasks": aggregate.total_tasks,
        "completed_tasks": aggregate.completed_tasks,
        "failed_tasks": aggregate.failed_tasks,
        "cancelled_tasks": aggregate.cancelled_tasks,
        "progress": aggregate.progress,
        "task_ids": task_ids,
        "mapping": [
            {
                "symbol": child.symbol,
                "stock_code": child.stock_code,
                "task_id": child.task_id,
            }
            for child in state.children
        ],
        "children": [_child_result(child) for child in state.children],
        "summary": _summary(aggregate),
        "links": {"batch": f"/tasks?batch_id={state.batch_id}"},
        "message": _message(aggregate),
    }


def _count_children(state: BatchWorkflowState, status: ChildStatus) -> int:
    return sum(1 for child in state.children if child.status == status)


def _child_result(child: BatchChildState) -> dict[str, Any]:
    result: dict[str, Any] = {
        "symbol": child.symbol,
        "stock_code": child.stock_code,
        "task_id": child.task_id,
        "status": child.status,
        "progress": child.progress,
    }
    if child.analysis_id:
        result["analysis_id"] = child.analysis_id
    if child.report_url:
        result["report_url"] = child.report_url
    if child.error:
        result["error"] = child.error
    return result


def _summary(aggregate: BatchAggregate) -> str:
    return (
        "批量分析状态："
        f"{aggregate.completed_tasks}/{aggregate.total_tasks} 成功，"
        f"{aggregate.failed_tasks} 失败，"
        f"{aggregate.cancelled_tasks} 取消。"
    )


def _message(aggregate: BatchAggregate) -> str:
    if aggregate.status == "completed":
        return "批量分析已完成。"
    if aggregate.status == "partial":
        return "批量分析部分完成。"
    if aggregate.status == "failed":
        return "批量分析失败。"
    if aggregate.status == "cancelled":
        return "批量分析已取消。"
    return "批量分析任务处理中。"
