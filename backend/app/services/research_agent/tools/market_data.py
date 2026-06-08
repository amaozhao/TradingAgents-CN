from __future__ import annotations

from typing import Any

from ..context import ToolExecutionContext
from ..permissions import MARKET_DATA_READ
from ..registry import ResearchTool


async def _market_data_lookup(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "market_data_lookup", "accepted": True, "payload": payload}


def market_data_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="market_data_lookup",
            description="Look up TradingAgents-CN market data snippets for a symbol.",
            permission=MARKET_DATA_READ,
            schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
            handler=_market_data_lookup,
        )
    ]
