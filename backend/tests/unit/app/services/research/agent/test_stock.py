from __future__ import annotations

from asyncio import to_thread
from typing import Any

import pytest

from app.services.research.agent.command import (
    StockAnalysisCommand,
    normalize_stock_symbol_for_analysis,
)
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.emitter import StockWorkflowEventAdapter


def test_legacy_stock_payload_builds_analysis_parameters() -> None:
    command = StockAnalysisCommand.from_payload(
        {
            "stock_code": "SH600519",
            "market_type": "CN",
            "analysis_date": "2026-06-13",
            "depth": 4,
            "analysts": ["市场分析师", "基本面分析师", "社媒分析师"],
            "include_sentiment": True,
            "include_risk": False,
            "language": "zh-CN",
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-max",
            "custom_prompt": "重点解释估值风险",
        },
        resolve_models=lambda _payload: ("qwen-turbo", "qwen-max"),
    )
    parameters = command.parameters

    assert command.symbol == "600519"
    assert command.market_type == "A股"
    assert parameters.market_type == "A股"
    assert parameters.analysis_date.isoformat() == "2026-06-13T00:00:00"
    assert parameters.research_depth == "深度"
    assert parameters.selected_analysts == ["market", "fundamentals"]
    assert parameters.include_sentiment is True
    assert parameters.include_risk is False
    assert parameters.language == "zh-CN"
    assert parameters.quick_analysis_model == "qwen-turbo"
    assert parameters.deep_analysis_model == "qwen-max"
    assert parameters.custom_prompt == "重点解释估值风险"
    assert {"stage": "social_analysis", "reason": "A 股默认禁用社媒分析。"} in command.skipped_stages
    assert {"stage": "risk_review", "reason": "用户关闭风险评估。"} in command.skipped_stages
    skipped = {item["stage"]: item for item in command.stage_plan if item["status"] == "skipped"}
    assert skipped["social_analysis"]["reason"] == "A 股默认禁用社媒分析。"
    assert skipped["news_analysis"]["reason"] == "未选择该分析师。"
    assert skipped["risk_review"]["reason"] == "用户关闭风险评估。"


def test_stock_symbol_normalization_keeps_market_specific_formats() -> None:
    assert normalize_stock_symbol_for_analysis("0700.HK", None) == ("0700", "港股")
    assert normalize_stock_symbol_for_analysis("hk9988", "A股") == ("9988", "港股")
    assert normalize_stock_symbol_for_analysis("aapl.us", "A股") == ("AAPL", "美股")
    assert normalize_stock_symbol_for_analysis("000001", "US") == ("000001", "美股")


@pytest.mark.asyncio
async def test_stock_workflow_node_emitter_maps_nodes_to_stage_events() -> None:
    emitted: list[dict[str, Any]] = []

    async def emit(event: dict[str, Any]) -> None:
        emitted.append(event)

    context = ToolExecutionContext(
        principal=ResearchPrincipal.from_user(
            {"id": "user-1", "username": "alice", "is_admin": False, "roles": []}
        ),
        session_id="session-1",
        request_id="attempt-1",
        event_emitter=emit,
    )

    node_emitter = StockWorkflowEventAdapter.node_emitter(
        context=context,
        task_id="task-1",
        batch_id="batch-1",
    )
    assert node_emitter is not None

    await to_thread(node_emitter, "Market Analyst", "START")
    await to_thread(node_emitter, "Portfolio Manager", "Risk Judge")

    assert emitted[0] == {
        "tool_name": "stock_analysis",
        "mode": "single",
        "stage": "market_analysis",
        "title": "市场分析师",
        "status": "completed",
        "progress": 30,
        "message": "市场分析师已完成。",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "node": "Market Analyst",
        "edge_from": "START",
        "edge_to": "Market Analyst",
        "batch_id": "batch-1",
    }
    assert emitted[1] == {
        "tool_name": "stock_analysis",
        "mode": "single",
        "stage": "final_risk_decision",
        "title": "最终风险决策",
        "status": "completed",
        "progress": 97,
        "message": "最终风险决策已完成。",
        "task_id": "task-1",
        "attempt_id": "attempt-1",
        "node": "Portfolio Manager",
        "edge_from": "Risk Judge",
        "edge_to": "Portfolio Manager",
        "batch_id": "batch-1",
    }
