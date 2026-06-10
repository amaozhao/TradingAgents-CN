from __future__ import annotations

from typing import Any

from ...context import ToolExecutionContext
from ...permissions import MARKET_DATA_READ
from ...registry import ResearchTool
from .series import lookup_market_snapshot, normalize_symbol


async def _market_data_lookup(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    symbol = normalize_symbol(payload.get("symbol") or payload.get("code"))
    if not symbol:
        raise ValueError("symbol is required")
    snapshot = await lookup_market_snapshot(
        symbol,
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        limit=int(payload.get("limit") or 120),
    )
    return {
        "tool": "market_data_lookup",
        "accepted": True,
        **snapshot,
        "data_limitations": [
            "History may come from PostgreSQL cache or free data providers.",
            "Missing optional fields mean the upstream source did not expose them.",
        ],
    }


def market_data_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="market_data_lookup",
            description="Look up current-project market data snippets for a symbol.",
            permission=MARKET_DATA_READ,
            schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["symbol"],
            },
            handler=_market_data_lookup,
        )
    ]
