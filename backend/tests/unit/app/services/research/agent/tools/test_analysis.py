from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.tools import analysis as analysis_tools


def _tool_context() -> ToolExecutionContext:
    principal = ResearchPrincipal.from_user(
        {"id": "user-1", "username": "alice", "is_admin": False, "roles": []},
        session_id="session-1",
    )
    return ToolExecutionContext(principal=principal, session_id="session-1")


@pytest.mark.asyncio
async def test_batch_stock_analysis_delegates_to_batch_workflow(monkeypatch) -> None:
    calls: list[tuple[ToolExecutionContext, dict[str, Any]]] = []

    class FakeWorkflow:
        def __init__(self, *, tool_name: str) -> None:
            assert tool_name == "batch_stock_analysis"

        async def submit(
            self,
            context: ToolExecutionContext,
            payload: dict[str, Any],
        ) -> dict[str, Any]:
            calls.append((context, payload))
            return {
                "tool": "batch_stock_analysis",
                "mode": "batch",
                "accepted": True,
                "status": "processing",
                "batch_id": "batch-1",
                "task_ids": ["task-1", "task-2"],
                "mapping": [
                    {"symbol": "600036", "stock_code": "600036", "task_id": "task-1"},
                    {"symbol": "000001", "stock_code": "000001", "task_id": "task-2"},
                ],
                "links": {"batch": "/tasks?batch_id=batch-1"},
            }

    monkeypatch.setattr(analysis_tools, "BatchStockWorkflow", FakeWorkflow)

    result = await analysis_tools._batch_stock_analysis(
        _tool_context(),
        {"title": "批量分析", "symbols": ["600036", "000001"]},
    )

    assert len(calls) == 1
    assert result["tool"] == "batch_stock_analysis"
    assert result["mode"] == "batch"
    assert result["accepted"] is True
    assert result["batch_id"] == "batch-1"
    assert result["task_ids"] == ["task-1", "task-2"]
    assert result["mapping"][0]["symbol"] == "600036"
    assert result["links"] == {"batch": "/tasks?batch_id=batch-1"}
    assert "payload" not in result


@pytest.mark.asyncio
async def test_batch_stock_analysis_waits_when_requested(monkeypatch) -> None:
    called: list[str] = []

    class FakeWorkflow:
        def __init__(self, *, tool_name: str) -> None:
            assert tool_name == "batch_stock_analysis"

        async def submit(
            self,
            _context: ToolExecutionContext,
            _payload: dict[str, Any],
        ) -> dict[str, Any]:
            called.append("submit")
            return {}

        async def run_until_complete(
            self,
            _context: ToolExecutionContext,
            _payload: dict[str, Any],
        ) -> dict[str, Any]:
            called.append("run_until_complete")
            return {"tool": "batch_stock_analysis", "status": "completed"}

    monkeypatch.setattr(analysis_tools, "BatchStockWorkflow", FakeWorkflow)

    result = await analysis_tools._batch_stock_analysis(
        _tool_context(),
        {
            "title": "批量分析",
            "symbols": ["600036"],
            "wait_for_completion": True,
        },
    )

    assert called == ["run_until_complete"]
    assert result["status"] == "completed"


def test_batch_stock_analysis_schema_supports_batch_request_fields() -> None:
    tool = next(
        tool for tool in analysis_tools.analysis_tools() if tool.name == "batch_stock_analysis"
    )
    properties = tool.schema["properties"]

    assert {
        "title",
        "description",
        "symbols",
        "stock_codes",
        "market_type",
        "analysis_date",
        "research_depth",
        "selected_analysts",
        "analysts",
        "include_sentiment",
        "include_risk",
        "language",
        "quick_analysis_model",
        "deep_analysis_model",
        "strict_symbols",
        "max_concurrency",
        "wait_for_completion",
    }.issubset(properties)
    assert tool.schema["required"] == ["symbols"]
