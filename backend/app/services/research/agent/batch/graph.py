from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BatchWorkflowNode = Literal[
    "START",
    "validate_batch_request",
    "resolve_batch_parameters",
    "check_model_keys",
    "create_batch_record",
    "create_child_tasks",
    "submit_child_workflows",
    "run_child_workflows",
    "persist_child_results",
    "aggregate_batch_status",
    "persist_batch_result",
    "emit_finished",
    "END",
]


@dataclass(frozen=True)
class ConditionalEdge:
    source: BatchWorkflowNode
    condition: str
    target: BatchWorkflowNode | str


@dataclass(frozen=True)
class BatchStockWorkflowPlan:
    nodes: list[BatchWorkflowNode]
    normal_edges: list[tuple[BatchWorkflowNode, BatchWorkflowNode]]
    conditional_edges: list[ConditionalEdge]


def build_batch_stock_workflow_plan() -> BatchStockWorkflowPlan:
    nodes: list[BatchWorkflowNode] = [
        "START",
        "validate_batch_request",
        "resolve_batch_parameters",
        "check_model_keys",
        "create_batch_record",
        "create_child_tasks",
        "submit_child_workflows",
        "run_child_workflows",
        "persist_child_results",
        "aggregate_batch_status",
        "persist_batch_result",
        "emit_finished",
        "END",
    ]
    normal_edges: list[tuple[BatchWorkflowNode, BatchWorkflowNode]] = [
        ("START", "validate_batch_request"),
        ("validate_batch_request", "resolve_batch_parameters"),
        ("resolve_batch_parameters", "check_model_keys"),
        ("check_model_keys", "create_batch_record"),
        ("create_batch_record", "create_child_tasks"),
        ("create_child_tasks", "submit_child_workflows"),
        ("run_child_workflows", "persist_child_results"),
        ("persist_child_results", "aggregate_batch_status"),
        ("aggregate_batch_status", "persist_batch_result"),
        ("persist_batch_result", "emit_finished"),
        ("emit_finished", "END"),
    ]
    conditional_edges = [
        ConditionalEdge(
            "validate_batch_request",
            "no symbols",
            "END(config_required)",
        ),
        ConditionalEdge(
            "validate_batch_request",
            "symbols > 10",
            "END(config_required)",
        ),
        ConditionalEdge(
            "validate_batch_request",
            "invalid symbols and strict_symbols=true",
            "END(config_required)",
        ),
        ConditionalEdge(
            "validate_batch_request",
            "invalid symbols and strict_symbols=false",
            "resolve_batch_parameters",
        ),
        ConditionalEdge("check_model_keys", "missing API keys", "END(config_required)"),
        ConditionalEdge("submit_child_workflows", "wait_for_completion=false", "END"),
        ConditionalEdge(
            "submit_child_workflows",
            "wait_for_completion=true",
            "run_child_workflows",
        ),
        ConditionalEdge("aggregate_batch_status", "all completed", "completed"),
        ConditionalEdge("aggregate_batch_status", "all failed", "failed"),
        ConditionalEdge("aggregate_batch_status", "mixed completed/failed", "partial"),
        ConditionalEdge(
            "aggregate_batch_status",
            "cancelled children exist and unfinished remain",
            "cancelled or partial",
        ),
    ]
    return BatchStockWorkflowPlan(
        nodes=nodes,
        normal_edges=normal_edges,
        conditional_edges=conditional_edges,
    )
