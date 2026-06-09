from __future__ import annotations

from typing import Any

from app.services.research_agent.goals import ResearchGoalService

from ..context import ToolExecutionContext
from ..permissions import GOAL_EVIDENCE_WRITE, GOAL_READ, GOAL_WRITE
from ..registry import ResearchTool


async def _start_research_goal(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    if not context.session_id:
        raise ValueError("session_id is required")
    return await ResearchGoalService().create_goal(
        principal=context.principal,
        session_id=str(context.session_id),
        title=str(payload.get("title") or payload.get("goal") or "研究目标"),
        description=str(payload.get("description") or ""),
        criteria=list(payload.get("criteria") or []),
    )


async def _get_research_goal(
    context: ToolExecutionContext, _payload: dict[str, Any]
) -> dict[str, Any]:
    if not context.session_id:
        raise ValueError("session_id is required")
    goal = await ResearchGoalService().get_goal(
        str(context.session_id), context.principal.user_id
    )
    return goal or {"status": "not_found"}


async def _update_research_goal_status(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    if not context.session_id:
        raise ValueError("session_id is required")
    goal = await ResearchGoalService().update_status(
        session_id=str(context.session_id),
        user_id=context.principal.user_id,
        expected_goal_id=str(payload.get("expected_goal_id") or payload.get("goal_id") or ""),
        status=str(payload.get("status") or "active"),
        reason=str(payload.get("reason") or ""),
    )
    return goal or {"status": "not_found"}


async def _add_goal_evidence(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    if not context.session_id:
        raise ValueError("session_id is required")
    goal = await ResearchGoalService().add_evidence(
        session_id=str(context.session_id),
        user_id=context.principal.user_id,
        expected_goal_id=str(payload.get("expected_goal_id") or payload.get("goal_id") or ""),
        evidence=dict(payload.get("evidence") or payload),
    )
    return goal or {"status": "not_found"}


def goal_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="start_research_goal",
            description="Create a current-project research goal for this session.",
            permission=GOAL_WRITE,
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "criteria": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title"],
            },
            handler=_start_research_goal,
        ),
        ResearchTool(
            name="get_research_goal",
            description="Get the current owner-scoped research goal for this session.",
            permission=GOAL_READ,
            schema={"type": "object", "additionalProperties": True},
            handler=_get_research_goal,
        ),
        ResearchTool(
            name="update_research_goal_status",
            description="Update current research goal status with stale goal protection.",
            permission=GOAL_WRITE,
            schema={
                "type": "object",
                "properties": {
                    "expected_goal_id": {"type": "string"},
                    "status": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["expected_goal_id", "status"],
            },
            handler=_update_research_goal_status,
        ),
        ResearchTool(
            name="add_goal_evidence",
            description="Attach evidence to the current research goal.",
            permission=GOAL_EVIDENCE_WRITE,
            schema={
                "type": "object",
                "properties": {
                    "expected_goal_id": {"type": "string"},
                    "evidence": {"type": "object"},
                },
                "required": ["expected_goal_id", "evidence"],
            },
            handler=_add_goal_evidence,
        ),
    ]
