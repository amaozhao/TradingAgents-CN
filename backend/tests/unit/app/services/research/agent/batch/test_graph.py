from app.services.research.agent.batch.graph import build_batch_stock_workflow_plan


def test_batch_workflow_plan_lists_target_nodes():
    plan = build_batch_stock_workflow_plan()

    assert plan.nodes == [
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


def test_batch_workflow_plan_preserves_submission_first_edges():
    plan = build_batch_stock_workflow_plan()

    assert ("START", "validate_batch_request") in plan.normal_edges
    assert (
        "validate_batch_request",
        "resolve_batch_parameters",
    ) in plan.normal_edges
    assert ("resolve_batch_parameters", "check_model_keys") in plan.normal_edges
    assert ("check_model_keys", "create_batch_record") in plan.normal_edges
    assert ("create_batch_record", "create_child_tasks") in plan.normal_edges
    assert ("create_child_tasks", "submit_child_workflows") in plan.normal_edges
    assert ("run_child_workflows", "persist_child_results") in plan.normal_edges
    assert ("persist_child_results", "aggregate_batch_status") in plan.normal_edges
    assert ("aggregate_batch_status", "persist_batch_result") in plan.normal_edges
    assert ("persist_batch_result", "emit_finished") in plan.normal_edges
    assert ("emit_finished", "END") in plan.normal_edges

    assert any(
        edge.source == "submit_child_workflows"
        and edge.condition == "wait_for_completion=false"
        and edge.target == "END"
        for edge in plan.conditional_edges
    )
    assert any(
        edge.source == "submit_child_workflows"
        and edge.condition == "wait_for_completion=true"
        and edge.target == "run_child_workflows"
        for edge in plan.conditional_edges
    )


def test_batch_workflow_plan_models_validation_and_terminal_conditions():
    plan = build_batch_stock_workflow_plan()
    conditions = {
        (edge.source, edge.condition, edge.target) for edge in plan.conditional_edges
    }

    assert (
        "validate_batch_request",
        "no symbols",
        "END(config_required)",
    ) in conditions
    assert (
        "validate_batch_request",
        "symbols > 10",
        "END(config_required)",
    ) in conditions
    assert (
        "validate_batch_request",
        "invalid symbols and strict_symbols=true",
        "END(config_required)",
    ) in conditions
    assert ("check_model_keys", "missing API keys", "END(config_required)") in conditions
    assert ("aggregate_batch_status", "all completed", "completed") in conditions
    assert ("aggregate_batch_status", "all failed", "failed") in conditions
    assert ("aggregate_batch_status", "mixed completed/failed", "partial") in conditions
