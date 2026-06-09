from __future__ import annotations

import re
from typing import Any

from app.services.research_agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import SHADOW_RUN
from ..registry import ResearchTool


def _requires_session(context: ToolExecutionContext) -> str:
    if not context.session_id:
        raise ValueError("session_id is required")
    return str(context.session_id)


async def _create_shadow_artifact(
    context: ToolExecutionContext,
    *,
    artifact_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await ResearchArtifactService().create_artifact(
        session_id=_requires_session(context),
        user_id=context.principal.user_id,
        artifact_type=artifact_type,
        payload=payload,
    )


async def _extract_shadow_strategy(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    description = str(payload.get("description") or payload.get("strategy") or "").strip()
    if not description:
        raise ValueError("description is required")
    tokens = re.findall(r"[A-Za-z0-9_\-.]+|[\u4e00-\u9fff]+", description)
    strategy = {
        "name": str(payload.get("name") or "shadow_strategy"),
        "description": description,
        "keywords": tokens[:20],
        "entry_rules": payload.get("entry_rules") or [],
        "exit_rules": payload.get("exit_rules") or [],
        "risk_rules": payload.get("risk_rules") or [],
        "research_only": True,
    }
    artifact = await _create_shadow_artifact(
        context, artifact_type="shadow_strategy", payload=strategy
    )
    return {
        "tool": "extract_shadow_strategy",
        "status": "completed",
        "strategy_id": artifact["artifact_id"],
        "artifact_id": artifact["artifact_id"],
        "strategy": strategy,
    }


def _numeric_values(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    out: list[float] = []
    for item in values:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out


async def _run_shadow_backtest(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    returns = _numeric_values(payload.get("returns"))
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    trade_pnl = _numeric_values([
        item.get("pnl") for item in trades if isinstance(item, dict)
    ])
    series = returns or trade_pnl
    if not series:
        return {
            "tool": "run_shadow_backtest",
            "status": "config_required",
            "accepted": False,
            "reason": "returns or trades[].pnl is required; the agent will not fabricate market data.",
        }
    total_return = sum(series)
    win_rate = len([value for value in series if value > 0]) / len(series)
    max_loss = min(series)
    metrics = {
        "observations": len(series),
        "total_return": total_return,
        "average_return": total_return / len(series),
        "win_rate": win_rate,
        "max_loss": max_loss,
    }
    artifact = await _create_shadow_artifact(
        context,
        artifact_type="shadow_backtest",
        payload={
            "strategy_id": payload.get("strategy_id"),
            "metrics": metrics,
            "returns": series,
            "research_only": True,
        },
    )
    return {
        "tool": "run_shadow_backtest",
        "status": "completed",
        "backtest_id": artifact["artifact_id"],
        "artifact_id": artifact["artifact_id"],
        "metrics": metrics,
    }


async def _render_shadow_report(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    summary = str(payload.get("summary") or "Shadow research report").strip()
    report = {
        "shadow_id": str(payload.get("shadow_id") or payload.get("backtest_id") or ""),
        "strategy_id": payload.get("strategy_id"),
        "backtest_id": payload.get("backtest_id"),
        "summary": summary,
        "risks": list(payload.get("risks") or []),
        "next_steps": list(payload.get("next_steps") or []),
        "research_only": True,
    }
    artifact = await _create_shadow_artifact(
        context, artifact_type="shadow_report", payload=report
    )
    return {
        "tool": "render_shadow_report",
        "status": "completed",
        "shadow_id": report["shadow_id"] or artifact["artifact_id"],
        "artifact_id": artifact["artifact_id"],
        "report": report,
    }


async def _scan_shadow_signals(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    signals = payload.get("signals")
    if not isinstance(signals, list) or not signals:
        return {
            "tool": "scan_shadow_signals",
            "status": "config_required",
            "accepted": False,
            "reason": "signals are required; the agent will not fabricate signal scans.",
        }
    return {
        "tool": "scan_shadow_signals",
        "status": "completed",
        "signals": signals[:50],
        "count": min(len(signals), 50),
    }


def shadow_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="extract_shadow_strategy",
            description="Extract a research-only shadow strategy artifact from a strategy description.",
            permission=SHADOW_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_extract_shadow_strategy,
        ),
        ResearchTool(
            name="run_shadow_backtest",
            description="Run a research-only shadow backtest from provided returns or trade PnL data.",
            permission=SHADOW_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_run_shadow_backtest,
        ),
        ResearchTool(
            name="render_shadow_report",
            description="Render a current-project shadow report artifact.",
            permission=SHADOW_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_render_shadow_report,
        ),
        ResearchTool(
            name="scan_shadow_signals",
            description="Scan provided shadow signals without fabricating market data.",
            permission=SHADOW_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_scan_shadow_signals,
        ),
    ]
