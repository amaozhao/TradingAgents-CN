from __future__ import annotations

from typing import Any

from app.services.research.agent.swarm import ResearchSwarmService

from ..context import ToolExecutionContext
from ..permissions import SWARM_RUN
from ..registry import ResearchTool


async def _run_swarm(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    service = ResearchSwarmService()
    run = await service.create_run(
        principal=context.principal,
        preset=str(payload.get("preset") or "research_team"),
        variables=dict(payload.get("variables") or {}),
        session_id=str(context.session_id) if context.session_id else None,
    )
    completed = await service.execute_run(
        principal=context.principal,
        run_id=run["run_id"],
    )
    final_run = completed or run
    return {
        "tool": "run_swarm",
        "status": final_run["status"],
        "run_id": final_run["run_id"],
        "preset": final_run["preset"],
        "workers": final_run["workers"],
        "summaries": final_run.get("summaries", []),
    }


def swarm_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="run_swarm",
            description="Start a current-project research-only swarm run and relay its events into the parent Agent session.",
            permission=SWARM_RUN,
            schema={
                "type": "object",
                "properties": {
                    "preset": {
                        "type": "string",
                        "enum": ["investment_committee", "research_team"],
                    },
                    "variables": {"type": "object"},
                },
            },
            handler=_run_swarm,
        )
    ]
