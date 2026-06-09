from __future__ import annotations

import re
import statistics
import uuid
from typing import Any

from app.services.research_agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import TRADE_JOURNAL_ANALYZE
from ..registry import ResearchTool


_PNL_PATTERN = re.compile(
    r"(?:pnl|p&l|profit|loss|盈亏|收益|亏损)\s*[:=：]?\s*([+-]?\s*(?:[$￥¥])?\s*\d+(?:\.\d+)?\s*%?)",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"([+-]?\s*(?:[$￥¥])?\s*\d+(?:\.\d+)?\s*%?)")
_RISK_KEYWORDS = (
    "breach",
    "violate",
    "violation",
    "overtrade",
    "over-trade",
    "revenge",
    "stop loss",
    "stopped out",
    "纪律",
    "违规",
    "超额",
    "过度交易",
    "报复性交易",
    "止损",
    "风控",
)


def _to_float(value: str) -> float | None:
    cleaned = (
        value.replace("$", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace(",", "")
        .replace(" ", "")
        .replace("%", "")
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_pnl(line: str) -> float | None:
    match = _PNL_PATTERN.search(line)
    if match:
        raw_value = match.group(1)
        value = _to_float(raw_value)
        if value is None:
            return None
        lowered = line.lower()
        explicit_sign = raw_value.strip().startswith(("+", "-"))
        if not explicit_sign and any(word in lowered for word in ("loss", "亏损")):
            return -abs(value)
        if not explicit_sign and any(word in lowered for word in ("profit", "收益", "盈利")):
            return abs(value)
        return value
    lowered = line.lower()
    if any(word in lowered for word in ("win", "profit", "收益", "盈利")):
        match = _NUMBER_PATTERN.search(line)
        if match:
            value = _to_float(match.group(1))
            return value if value is None or value >= 0 else abs(value)
    if any(word in lowered for word in ("loss", "亏损")):
        match = _NUMBER_PATTERN.search(line)
        if match:
            value = _to_float(match.group(1))
            return value if value is None or value <= 0 else -abs(value)
    return None


async def _load_journal_text(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    text = str(payload.get("text") or "").strip()
    if text:
        return text, {"source": "text"}

    artifact_id = str(payload.get("artifact_id") or payload.get("file_id") or "").strip()
    if not artifact_id:
        return "", {"source": "missing"}

    artifact = await ResearchArtifactService().get_artifact(
        artifact_id, context.principal.user_id
    )
    if not artifact:
        return "", {"source": "artifact", "artifact_id": artifact_id, "status": "not_found"}

    payload_data = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else {}
    artifact_text = str(payload_data.get("text") or payload_data.get("content") or "").strip()
    return artifact_text, {
        "source": "artifact",
        "artifact_id": artifact_id,
        "artifact_type": artifact.get("artifact_type"),
        "filename": payload_data.get("filename"),
    }


async def _analyze_trade_journal(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    text, source = await _load_journal_text(context, payload)
    if not text:
        return {
            "tool": "analyze_trade_journal",
            "status": "config_required",
            "accepted": False,
            "reason": "Provide journal text or an owner-scoped uploaded artifact_id/file_id; no synthetic trade data is generated.",
            "source": source,
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pnls: list[float] = []
    risk_flags: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for index, line in enumerate(lines, start=1):
        pnl = _extract_pnl(line)
        if pnl is not None:
            pnls.append(pnl)
        for symbol in re.findall(r"\b(?:\d{6}\.(?:SH|SZ)|[A-Z]{1,6})\b", line):
            symbols.add(symbol)
        lowered = line.lower()
        matched = [keyword for keyword in _RISK_KEYWORDS if keyword in lowered or keyword in line]
        if matched:
            risk_flags.append(
                {
                    "line": index,
                    "keywords": matched[:5],
                    "preview": line[:240],
                }
            )

    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    flat = [value for value in pnls if value == 0]
    metrics = {
        "entries": len(lines),
        "trades_with_pnl": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "flat": len(flat),
        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
        "total_pnl": round(sum(pnls), 6) if pnls else None,
        "average_pnl": round(statistics.fmean(pnls), 6) if pnls else None,
        "best_pnl": max(pnls) if pnls else None,
        "worst_pnl": min(pnls) if pnls else None,
        "symbols": sorted(symbols)[:50],
        "risk_flag_count": len(risk_flags),
    }
    artifact_id = None
    if context.session_id:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=context.session_id,
            user_id=context.principal.user_id,
            artifact_type="trade_journal_analysis",
            payload={
                "analysis_id": str(uuid.uuid4()),
                "source": source,
                "metrics": metrics,
                "risk_flags": risk_flags,
            },
        )
        artifact_id = artifact["artifact_id"]

    return {
        "tool": "analyze_trade_journal",
        "status": "completed",
        "accepted": True,
        "source": source,
        "metrics": metrics,
        "risk_flags": risk_flags,
        "artifact_id": artifact_id,
    }


def journal_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="analyze_trade_journal",
            description="Analyze owner-scoped trade journal text or uploaded artifacts for PnL and risk-discipline signals.",
            permission=TRADE_JOURNAL_ANALYZE,
            schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "artifact_id": {"type": "string"},
                    "file_id": {"type": "string"},
                },
            },
            handler=_analyze_trade_journal,
        )
    ]
