from __future__ import annotations

from typing import Any

from app.services.research_agent.memory import (
    ResearchHypothesisService,
    ResearchMemoryService,
)

from ..context import ToolExecutionContext
from ..permissions import HYPOTHESIS_READ, HYPOTHESIS_WRITE, MEMORY_WRITE
from ..registry import ResearchTool


async def _remember(context: ToolExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
    content = str(payload.get("content") or payload.get("memory") or "").strip()
    if not content:
        raise ValueError("content is required")
    item = await ResearchMemoryService().remember(
        principal=context.principal,
        session_id=str(context.session_id) if context.session_id else None,
        content=content,
        metadata=dict(payload.get("metadata") or {}),
    )
    return {"tool": "remember", "status": "completed", "memory": item}


async def _create_hypothesis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    statement = str(payload.get("statement") or payload.get("hypothesis") or "").strip()
    title = str(payload.get("title") or "").strip()
    thesis = str(
        payload.get("thesis")
        or payload.get("description")
        or statement
        or payload.get("rationale")
        or ""
    ).strip()
    if not title and statement:
        title = statement[:120]
    if not title or not thesis:
        raise ValueError("title and thesis are required")
    item = await ResearchHypothesisService().create(
        principal=context.principal,
        session_id=str(context.session_id) if context.session_id else None,
        title=title,
        thesis=thesis,
        evidence=_list_value(payload.get("evidence")),
        status=str(payload.get("status") or "open"),
    )
    return {"tool": "create_hypothesis", "status": "completed", "hypothesis": item}


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "item", "values", "value"):
            if key in value:
                return _list_value(value.get(key))
        return [value]
    return [value]


async def _update_hypothesis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    hypothesis_id = str(payload.get("hypothesis_id") or "").strip()
    if not hypothesis_id:
        raise ValueError("hypothesis_id is required")
    item = await ResearchHypothesisService().update(
        hypothesis_id=hypothesis_id,
        user_id=context.principal.user_id,
        updates=payload,
    )
    return {"tool": "update_hypothesis", "status": "completed" if item else "not_found", "hypothesis": item}


async def _search_hypotheses(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    matches = await ResearchHypothesisService().search(
        user_id=context.principal.user_id, query=query
    )
    return {"tool": "search_hypotheses", "status": "completed", "matches": matches}


async def _link_backtest(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    hypothesis_id = str(payload.get("hypothesis_id") or "").strip()
    backtest_id = str(payload.get("backtest_id") or payload.get("artifact_id") or "").strip()
    if not hypothesis_id or not backtest_id:
        raise ValueError("hypothesis_id and backtest_id are required")
    item = await ResearchHypothesisService().link_backtest(
        hypothesis_id=hypothesis_id,
        user_id=context.principal.user_id,
        backtest_id=backtest_id,
        summary=str(payload.get("summary") or ""),
    )
    return {"tool": "link_backtest", "status": "completed" if item else "not_found", "hypothesis": item}


def memory_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="remember",
            description="Store an owner-scoped research memory in current-project storage.",
            permission=MEMORY_WRITE,
            schema={"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
            handler=_remember,
        ),
        ResearchTool(
            name="create_hypothesis",
            description="Create an owner-scoped research hypothesis ledger item.",
            permission=HYPOTHESIS_WRITE,
            schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "thesis": {"type": "string"},
                    "description": {"type": "string"},
                    "statement": {
                        "type": "string",
                        "description": "Alias for thesis; title is derived from this if omitted.",
                    },
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {}},
                    "status": {"type": "string"},
                },
                "additionalProperties": True,
            },
            handler=_create_hypothesis,
        ),
        ResearchTool(
            name="update_hypothesis",
            description="Update an owner-scoped research hypothesis.",
            permission=HYPOTHESIS_WRITE,
            schema={"type": "object", "additionalProperties": True},
            handler=_update_hypothesis,
        ),
        ResearchTool(
            name="search_hypotheses",
            description="Search owner-scoped research hypotheses.",
            permission=HYPOTHESIS_READ,
            schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            handler=_search_hypotheses,
        ),
        ResearchTool(
            name="link_backtest",
            description="Link a backtest artifact to an owner-scoped hypothesis.",
            permission=HYPOTHESIS_WRITE,
            schema={"type": "object", "additionalProperties": True},
            handler=_link_backtest,
        ),
    ]
