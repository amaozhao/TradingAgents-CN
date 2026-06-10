from __future__ import annotations

from typing import Any

from ..context import ToolExecutionContext
from ..permissions import BATCH_STOCK_ANALYSIS, SINGLE_STOCK_ANALYSIS
from ..registry import ResearchTool


async def _single_stock_analysis(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "single_stock_analysis", "accepted": True, "payload": payload}


async def _batch_stock_analysis(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "batch_stock_analysis", "accepted": True, "payload": payload}


def analysis_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="single_stock_analysis",
            description="Start or inspect a single-stock analysis workflow.",
            permission=SINGLE_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
            handler=_single_stock_analysis,
        ),
        ResearchTool(
            name="batch_stock_analysis",
            description="Start or inspect a batch stock analysis workflow.",
            permission=BATCH_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {"symbols": {"type": "array", "items": {"type": "string"}}},
                "required": ["symbols"],
            },
            handler=_batch_stock_analysis,
        ),
    ]
