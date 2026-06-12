"""Batch stock analysis workflow contracts."""

from .graph import BatchStockWorkflowPlan, ConditionalEdge, build_batch_stock_workflow_plan
from .runner import BatchStockWorkflow
from .state import (
    BatchAggregate,
    BatchChildState,
    BatchWorkflowState,
    aggregate_batch_status,
    build_batch_tool_result,
    normalize_batch_status_for_document,
)

__all__ = [
    "BatchAggregate",
    "BatchChildState",
    "BatchStockWorkflowPlan",
    "BatchStockWorkflow",
    "BatchWorkflowState",
    "ConditionalEdge",
    "aggregate_batch_status",
    "build_batch_stock_workflow_plan",
    "build_batch_tool_result",
    "normalize_batch_status_for_document",
]
