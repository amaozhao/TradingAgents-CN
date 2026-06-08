from __future__ import annotations

from typing import Any

from ..context import ToolExecutionContext
from ..permissions import REPORT_READ, REPORT_WRITE
from ..registry import ResearchTool


async def _report_lookup(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "report_lookup", "accepted": True, "payload": payload}


async def _report_write(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "report_write", "accepted": True, "payload": payload}


def report_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="report_lookup",
            description="Look up owner-scoped analysis report metadata and content.",
            permission=REPORT_READ,
            schema={
                "type": "object",
                "properties": {"report_id": {"type": "string"}},
            },
            handler=_report_lookup,
        ),
        ResearchTool(
            name="report_write",
            description="Write owner-scoped research report artifacts.",
            permission=REPORT_WRITE,
            schema={"type": "object", "additionalProperties": True},
            handler=_report_write,
        ),
    ]
