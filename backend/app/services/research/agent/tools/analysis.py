from __future__ import annotations

from typing import Any

from ..batch.runner import BatchStockWorkflow
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
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    workflow = BatchStockWorkflow(tool_name="batch_stock_analysis")
    if payload.get("wait_for_completion") is True:
        return await workflow.run_until_complete(context, payload)
    return await workflow.submit(context, payload)


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


def _batch_stock_analysis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 10,
            },
            "stock_codes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 10,
            },
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
            "selected_analysts": {"type": "array", "items": {"type": "string"}},
            "analysts": {"type": "array", "items": {"type": "string"}},
            "include_sentiment": {"type": "boolean"},
            "include_risk": {"type": "boolean"},
            "language": {"type": "string"},
            "quick_analysis_model": {"type": "string"},
            "deep_analysis_model": {"type": "string"},
            "strict_symbols": {"type": "boolean"},
            "max_concurrency": {"type": "number"},
            "wait_for_completion": {"type": "boolean"},
        },
        "required": ["symbols"],
    }


def analysis_tools() -> list[ResearchTool]:
    stock_analysis_schema = _stock_analysis_schema()
    batch_stock_analysis_schema = _batch_stock_analysis_schema()
    return [
        ResearchTool(
            name="stock_analysis",
            description=(
                "Run the owner-scoped Agent single-stock workflow. This workflow "
                "replicates the original TradingAgents DAG nodes, tools, debates, "
                "risk review, and report schema; it does not submit to the old "
                "analysis queue and does not use the simplified native workflow."
            ),
            permission=SINGLE_STOCK_ANALYSIS,
            schema=stock_analysis_schema,
            handler=_stock_analysis,
        ),
        ResearchTool(
            name="single_stock_analysis",
            description=(
                "Compatibility alias for stock_analysis. Runs the Agent DAG-parity "
                "single-stock workflow and returns the generated compatible report. "
                "Supports market_type, analysis_date, research_depth, selected_analysts, "
                "include_sentiment/include_risk, and quick/deep models."
            ),
            permission=SINGLE_STOCK_ANALYSIS,
            schema=stock_analysis_schema,
            handler=_single_stock_analysis,
        ),
        ResearchTool(
            name="stock_analysis_status",
            description="Read status/progress for an existing owner-scoped single-stock analysis task.",
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
            description="Read the completed owner-scoped single-stock analysis report by task_id.",
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
            description=(
                "Submit an owner-scoped batch stock workflow using the Agent "
                "DAG-parity single-stock workflow for each child stock. Supports "
                "the legacy BatchAnalysisRequest symbols/stock_codes fields."
            ),
            permission=BATCH_STOCK_ANALYSIS,
            schema=batch_stock_analysis_schema,
            handler=_batch_stock_analysis,
        ),
    ]
