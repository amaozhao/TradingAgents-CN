from datetime import UTC, datetime

from app.services.research.agent.batch.state import (
    BatchChildState,
    BatchWorkflowState,
    aggregate_batch_status,
    build_batch_tool_result,
    normalize_batch_status_for_document,
)


def _state(*children: BatchChildState) -> BatchWorkflowState:
    return BatchWorkflowState(
        batch_id="batch-1",
        user_id="user-1",
        title="批量分析",
        description="银行股批量分析",
        status="pending",
        parameters={"market_type": "A股"},
        children=list(children),
        created_at=datetime(2026, 6, 12, tzinfo=UTC),
    )


def _child(symbol: str, task_id: str, status: str) -> BatchChildState:
    return BatchChildState(symbol=symbol, stock_code=symbol, task_id=task_id, status=status)


def test_aggregate_batch_status_completed_when_all_children_completed():
    result = aggregate_batch_status(
        _state(
            _child("600036", "task-1", "completed"),
            _child("000001", "task-2", "completed"),
        )
    )

    assert result.status == "completed"
    assert result.total_tasks == 2
    assert result.completed_tasks == 2
    assert result.failed_tasks == 0
    assert result.cancelled_tasks == 0
    assert result.progress == 100


def test_aggregate_batch_status_failed_when_all_children_failed():
    result = aggregate_batch_status(
        _state(
            _child("600036", "task-1", "failed"),
            _child("000001", "task-2", "failed"),
        )
    )

    assert result.status == "failed"
    assert result.completed_tasks == 0
    assert result.failed_tasks == 2
    assert result.progress == 100


def test_aggregate_batch_status_partial_for_mixed_completed_and_failed_children():
    result = aggregate_batch_status(
        _state(
            _child("600036", "task-1", "completed"),
            _child("000001", "task-2", "failed"),
        )
    )

    assert result.status == "partial"
    assert result.completed_tasks == 1
    assert result.failed_tasks == 1
    assert result.progress == 100


def test_aggregate_batch_status_processing_counts_only_finished_children():
    result = aggregate_batch_status(
        _state(
            _child("600036", "task-1", "completed"),
            _child("000001", "task-2", "processing"),
        )
    )

    assert result.status == "processing"
    assert result.completed_tasks == 1
    assert result.failed_tasks == 0
    assert result.progress == 50


def test_aggregate_batch_status_cancelled_when_no_successful_results_remain():
    result = aggregate_batch_status(
        _state(
            _child("600036", "task-1", "cancelled"),
            _child("000001", "task-2", "cancelled"),
        )
    )

    assert result.status == "cancelled"
    assert result.cancelled_tasks == 2
    assert result.progress == 100


def test_partial_status_maps_to_document_partial_success_only_at_document_boundary():
    assert normalize_batch_status_for_document("partial") == "partial_success"
    assert normalize_batch_status_for_document("completed") == "completed"


def test_batch_tool_result_contains_legacy_mapping_and_batch_link():
    state = _state(
        _child("600036", "task-1", "completed"),
        _child("000001", "task-2", "failed"),
    )

    result = build_batch_tool_result(state)

    assert result["tool"] == "batch_stock_analysis"
    assert result["mode"] == "batch"
    assert result["accepted"] is True
    assert result["status"] == "partial"
    assert result["batch_id"] == "batch-1"
    assert result["task_ids"] == ["task-1", "task-2"]
    assert result["mapping"] == [
        {"symbol": "600036", "stock_code": "600036", "task_id": "task-1"},
        {"symbol": "000001", "stock_code": "000001", "task_id": "task-2"},
    ]
    assert result["links"] == {"batch": "/tasks?batch_id=batch-1"}
