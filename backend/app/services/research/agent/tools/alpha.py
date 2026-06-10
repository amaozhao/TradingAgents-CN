from __future__ import annotations

from typing import Any

from app.services.alpha.zoo.jobs import AlphaZooJobService
from app.services.alpha.zoo.service import AlphaZooService

from ..context import ToolExecutionContext
from ..permissions import ALPHA_READ, ALPHA_RUN
from ..registry import ResearchTool


async def _alpha_list(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return AlphaZooService().list_factors(
        family=payload.get("family"),
        search=payload.get("search"),
    )


async def _alpha_detail(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    alpha_id = str(payload.get("alpha_id") or "")
    factor = AlphaZooService().get_factor(alpha_id)
    if factor is None:
        raise KeyError(f"Unknown alpha ID: {alpha_id}")
    return factor


async def _alpha_bench(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await AlphaZooJobService().create_bench_job(
        principal=context.principal,
        alpha_id=str(payload.get("alpha_id") or ""),
        symbols=list(payload.get("symbols") or []),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
    )


async def _alpha_compare(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await AlphaZooJobService().create_compare_job(
        principal=context.principal,
        alpha_ids=list(payload.get("alpha_ids") or []),
        symbols=list(payload.get("symbols") or []),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
    )


def alpha_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="alpha_list",
            description="List available Alpha Zoo factors.",
            permission=ALPHA_READ,
            schema={"type": "object", "additionalProperties": True},
            handler=_alpha_list,
        ),
        ResearchTool(
            name="alpha_detail",
            description="Get metadata for one Alpha Zoo factor.",
            permission=ALPHA_READ,
            schema={
                "type": "object",
                "properties": {"alpha_id": {"type": "string"}},
                "required": ["alpha_id"],
            },
            handler=_alpha_detail,
        ),
        ResearchTool(
            name="alpha_bench",
            description="Run a private Alpha Zoo bench job.",
            permission=ALPHA_RUN,
            schema={
                "type": "object",
                "properties": {
                    "alpha_id": {"type": "string"},
                    "symbols": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["alpha_id"],
            },
            handler=_alpha_bench,
        ),
        ResearchTool(
            name="alpha_compare",
            description="Run a private Alpha Zoo compare job.",
            permission=ALPHA_RUN,
            schema={
                "type": "object",
                "properties": {
                    "alpha_ids": {"type": "array", "items": {"type": "string"}},
                    "symbols": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["alpha_ids"],
            },
            handler=_alpha_compare,
        ),
    ]
