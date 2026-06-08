from __future__ import annotations

from typing import Any

from ..context import ToolExecutionContext
from ..permissions import SCREENING_RUN
from ..registry import ResearchTool


async def _screening_run(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "screening_run", "accepted": True, "payload": payload}


def screening_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="screening_run",
            description="Run an owner-scoped stock screening query.",
            permission=SCREENING_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_screening_run,
        )
    ]
