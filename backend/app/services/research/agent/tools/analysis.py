from __future__ import annotations

from typing import Any

from ..context import ToolExecutionContext
from ..permissions import BATCH_STOCK_ANALYSIS, REPORT_READ, SINGLE_STOCK_ANALYSIS
from ..registry import ResearchTool
from ..stock import (
    StockAnalysisWorkflow,
    read_stock_analysis_report,
    read_stock_analysis_status,
)


async def _stock_analysis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await StockAnalysisWorkflow(tool_name="stock_analysis").run_single(
        context, payload
    )


async def _single_stock_analysis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await StockAnalysisWorkflow(tool_name="single_stock_analysis").run_single(
        context, payload
    )


async def _batch_stock_analysis(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "batch_stock_analysis", "accepted": True, "payload": payload}


async def _stock_analysis_status(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await read_stock_analysis_status(context, payload)


async def _stock_analysis_report(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await read_stock_analysis_report(context, payload)


def _stock_analysis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["single"]},
            "symbol": {"type": "string"},
            "stock_code": {"type": "string"},
            "market_type": {"type": "string", "enum": ["A股", "港股", "美股"]},
            "analysis_date": {"type": "string"},
            "research_depth": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": [
                            "快速",
                            "基础",
                            "标准",
                            "深度",
                            "全面",
                            "1",
                            "2",
                            "3",
                            "4",
                            "5",
                        ],
                    },
                    {"type": "number"},
                ]
            },
            "selected_analysts": {
                "type": "array",
                "items": {"type": "string"},
            },
            "analysts": {"type": "array", "items": {"type": "string"}},
            "include_sentiment": {"type": "boolean"},
            "include_risk": {"type": "boolean"},
            "language": {"type": "string"},
            "quick_analysis_model": {"type": "string"},
            "deep_analysis_model": {"type": "string"},
            "custom_prompt": {"type": "string"},
            "wait_for_completion": {"type": "boolean"},
            "wait_timeout_seconds": {"type": "number"},
            "poll_interval_seconds": {"type": "number"},
        },
    }


def analysis_tools() -> list[ResearchTool]:
    stock_analysis_schema = _stock_analysis_schema()
    return [
        ResearchTool(
            name="stock_analysis",
            description=(
                "Submit an owner-scoped single-stock analysis through the Agent-facing "
                "workflow wrapper. The first phase preserves the existing single-stock "
                "LangGraph DAG as the baseline and calls it through the current queue "
                "adapter without modifying DAG internals."
            ),
            permission=SINGLE_STOCK_ANALYSIS,
            schema=stock_analysis_schema,
            handler=_stock_analysis,
        ),
        ResearchTool(
            name="single_stock_analysis",
            description=(
                "Submit the existing single-stock TradingAgents LangGraph DAG to the "
                "analysis queue and wait for the resulting report by default. Supports "
                "market_type, analysis_date, research_depth, selected_analysts, "
                "include_sentiment/include_risk, quick/deep models, and wait controls."
            ),
            permission=SINGLE_STOCK_ANALYSIS,
            schema=stock_analysis_schema,
            handler=_single_stock_analysis,
        ),
        ResearchTool(
            name="stock_analysis_status",
            description="Read status/progress for an existing owner-scoped single-stock DAG task.",
            permission=SINGLE_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=_stock_analysis_status,
        ),
        ResearchTool(
            name="stock_analysis_report",
            description="Read the completed owner-scoped single-stock DAG report by task_id.",
            permission=REPORT_READ,
            schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=_stock_analysis_report,
        ),
        ResearchTool(
            name="batch_stock_analysis",
            description="Start or inspect a batch stock analysis workflow.",
            permission=BATCH_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["symbols"],
            },
            handler=_batch_stock_analysis,
        ),
    ]
