from __future__ import annotations

from typing import Any

from app.services.research_agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import REPORT_READ, REPORT_WRITE
from ..registry import ResearchTool


async def _report_lookup(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "report_lookup", "accepted": True, "payload": payload}


async def _report_write(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    if not context.session_id:
        raise ValueError("session_id is required to write a research report")

    report = build_structured_report(payload)
    artifact = await ResearchArtifactService().create_artifact(
        session_id=str(context.session_id),
        user_id=context.principal.user_id,
        artifact_type="research_report",
        payload=report,
    )
    return {
        "tool": "report_write",
        "accepted": True,
        "artifact_id": artifact["artifact_id"],
        "report": report,
    }


def build_structured_report(payload: dict[str, Any]) -> dict[str, Any]:
    sector = _mapping(payload.get("sector"))
    universe = _mapping(payload.get("universe"))
    correlation = _mapping(payload.get("correlation"))
    alpha = _mapping(payload.get("alpha"))
    single_stock_reports = _list_of_mappings(payload.get("single_stock_reports"))
    risk_factors = _string_list(payload.get("risk_factors"))
    data_limitations = _string_list(payload.get("data_limitations"))
    recommended_stocks = _list_of_mappings(payload.get("recommended_stocks"))
    linked_artifact_ids = _dedupe_strings(payload.get("artifact_ids"))
    linked_task_ids = _dedupe_strings(payload.get("task_ids"))

    for source in (correlation, alpha):
        artifact_id = source.get("artifact_id")
        if artifact_id:
            linked_artifact_ids = _append_unique(linked_artifact_ids, str(artifact_id))

    for report in single_stock_reports:
        task_id = report.get("task_id")
        if task_id:
            linked_task_ids = _append_unique(linked_task_ids, str(task_id))

    has_recommendation_evidence = bool(
        _string_list(correlation.get("findings"))
        or _string_list(alpha.get("findings"))
        or single_stock_reports
    )
    recommendation_limitation = ""
    if recommended_stocks and not has_recommendation_evidence:
        recommendation_limitation = "证据不足，暂不生成推荐个股。"
        recommended_stocks = []
        data_limitations = _append_unique(data_limitations, recommendation_limitation)

    sections = {
        "sector_summary": {
            "sector": str(sector.get("name") or payload.get("sector_name") or ""),
            "summary": str(sector.get("summary") or payload.get("sector_summary") or ""),
        },
        "universe_construction": {
            "method": str(universe.get("method") or ""),
            "symbols": _string_list(universe.get("symbols")),
            "description": str(universe.get("description") or ""),
        },
        "screening_filters": {
            "filters": _mapping(
                payload.get("screening_filters") or universe.get("filters")
            )
        },
        "correlation_findings": {
            "artifact_id": str(correlation.get("artifact_id") or ""),
            "findings": _string_list(correlation.get("findings")),
        },
        "alpha_factor_findings": {
            "artifact_id": str(alpha.get("artifact_id") or ""),
            "findings": _string_list(alpha.get("findings")),
        },
        "linked_single_stock_reports": {"reports": single_stock_reports},
        "recommended_stocks": {
            "items": recommended_stocks if has_recommendation_evidence else [],
            "limitation": recommendation_limitation,
        },
        "risk_factors": {"items": risk_factors},
        "data_limitations": {"items": data_limitations},
        "linked_artifacts_and_tasks": {
            "artifact_ids": linked_artifact_ids,
            "task_ids": linked_task_ids,
        },
    }
    return {
        "title": str(payload.get("title") or "研究报告"),
        "kind": "research_report",
        "sections": sections,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _dedupe_strings(value: Any) -> list[str]:
    return _append_many([], _string_list(value))


def _append_unique(items: list[str], item: str) -> list[str]:
    return items if item in items else [*items, item]


def _append_many(items: list[str], values: list[str]) -> list[str]:
    result = list(items)
    for value in values:
        result = _append_unique(result, value)
    return result


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
