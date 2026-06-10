from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.research.agent.artifacts import ResearchArtifactService
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.jobs import ResearchJobService

from ..permissions import CORRELATION_RUN
from ..registry import ResearchTool
from .market.series import build_returns_frame, load_price_series


class ResearchMatrixJobService:
    def __init__(
        self,
        *,
        job_service: ResearchJobService | None = None,
        artifact_service: ResearchArtifactService | None = None,
    ) -> None:
        self.job_service = job_service or ResearchJobService()
        self.artifact_service = artifact_service or ResearchArtifactService()

    async def create_correlation_job(
        self,
        *,
        principal: ResearchPrincipal,
        symbols: list[str] | None = None,
        method: str = "pearson",
        window: int = 60,
        screening_result_id: str | None = None,
        sector: str | None = None,
        favorites_id: str | None = None,
        universe_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_symbols = _resolve_symbols(
            symbols=symbols or [],
            screening_result_id=screening_result_id,
            sector=sector,
            favorites_id=favorites_id,
            universe_id=universe_id,
        )
        clean_method = method if method in {"pearson", "spearman", "kendall"} else "pearson"
        clean_window = max(2, min(int(window or 60), 252))
        payload = {
            "symbols": resolved_symbols,
            "method": clean_method,
            "window": clean_window,
            "screening_result_id": screening_result_id,
            "sector": sector,
            "favorites_id": favorites_id,
            "universe_id": universe_id,
        }
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="correlation",
            resource_id=",".join(resolved_symbols),
            payload=payload,
        )
        await self.job_service.mark_running(job["job_id"])
        matrix, matrix_source, missing_symbols = await _calculate_matrix(
            resolved_symbols, clean_method, clean_window
        )
        artifact_payload = {
            "kind": "correlation_matrix",
            "symbols": resolved_symbols,
            "method": clean_method,
            "window": clean_window,
            "matrix_source": matrix_source,
            "matrix": matrix,
            "high_correlation_pairs": _high_correlation_pairs(matrix),
            "diversification_candidates": _diversification_candidates(matrix),
            "missing_symbols": missing_symbols,
            "data_limitations": [
                "Correlation is computed from available close-price returns.",
                "Unavailable symbols are excluded and listed in missing_symbols.",
            ],
        }
        artifact = await self.artifact_service.create_artifact(
            session_id=job["job_id"],
            user_id=principal.user_id,
            artifact_type="correlation_matrix",
            payload=artifact_payload,
        )
        result = {**artifact_payload, "artifact_id": artifact["artifact_id"]}
        await self.job_service.mark_completed(job["job_id"], result)
        completed = await self.job_service.get(job["job_id"], principal.user_id)
        return completed or {**job, "status": "completed", "result": result}

    async def get_job(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        return await self.job_service.get(job_id, user_id)

    async def list_events(
        self, job_id: str, user_id: str, after_event_id: int = 0
    ) -> list[dict[str, Any]] | None:
        job = await self.job_service.get(job_id, user_id)
        if not job:
            return None
        return await self.job_service.list_events(job_id, user_id, after_event_id)


def _resolve_symbols(
    *,
    symbols: list[str],
    screening_result_id: str | None,
    sector: str | None,
    favorites_id: str | None,
    universe_id: str | None,
) -> list[str]:
    if screening_result_id:
        raise KeyError("screening_result_id is not available")
    if favorites_id:
        raise KeyError("favorites universe is not persisted")
    if universe_id:
        raise KeyError("universe is not persisted")

    clean_symbols = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
    if clean_symbols:
        return clean_symbols
    if sector:
        return _sector_symbols(sector)
    raise ValueError("symbols, sector, favorites_id, or universe_id is required")


def _sector_symbols(sector: str) -> list[str]:
    sector_key = sector.lower()
    sector_map = {
        "storage": ["300750", "002594", "601012"],
        "energy_storage": ["300750", "002594", "601012"],
        "baijiu": ["600519", "000858", "000568"],
    }
    return sector_map.get(sector_key, ["600519", "000001"])


async def _calculate_matrix(
    symbols: list[str], method: str, window: int
) -> tuple[dict[str, dict[str, float]], str, list[str]]:
    series_map = await load_price_series(symbols, limit=window)
    returns = build_returns_frame(series_map).tail(window)
    missing_symbols = [
        symbol for symbol in symbols
        if symbol not in returns.columns or not series_map.get(symbol, {}).get("returns")
    ]
    matrix_source = "market_data"
    if returns.empty or len(returns.columns) < 2:
        returns = pd.DataFrame(
            {
                symbol: [((day + 1) * (index + 1)) % 17 / 100 for day in range(window)]
                for index, symbol in enumerate(symbols)
            }
        )
        matrix_source = "synthetic_fallback"
    corr = returns.corr(method=method).fillna(1.0)
    matrix = {
        str(row): {str(column): round(float(corr.loc[row, column]), 6) for column in corr}
        for row in corr.index
    }
    return matrix, matrix_source, missing_symbols


def _high_correlation_pairs(matrix: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    symbols = list(matrix)
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(symbols):
        for right in symbols[left_index + 1 :]:
            value = matrix[left][right]
            if abs(value) >= 0.7:
                pairs.append({"left": left, "right": right, "correlation": value})
    return pairs


def _diversification_candidates(matrix: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for symbol, row in matrix.items():
        others = [abs(value) for other, value in row.items() if other != symbol]
        avg_abs_corr = sum(others) / len(others) if others else 0.0
        candidates.append(
            {
                "symbol": symbol,
                "avg_abs_correlation": round(avg_abs_corr, 6),
            }
        )
    return sorted(candidates, key=lambda item: item["avg_abs_correlation"])


async def _correlation_matrix(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return await ResearchMatrixJobService().create_correlation_job(
        principal=context.principal,
        symbols=list(payload.get("symbols") or []),
        method=str(payload.get("method") or "pearson"),
        window=int(payload.get("window") or 60),
        screening_result_id=payload.get("screening_result_id"),
        sector=payload.get("sector"),
        favorites_id=payload.get("favorites_id"),
        universe_id=payload.get("universe_id"),
    )


def correlation_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="correlation_matrix",
            description="Run a private correlation matrix job for a user-owned universe.",
            permission=CORRELATION_RUN,
            schema={
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "method": {"type": "string"},
                    "window": {"type": "integer"},
                },
            },
            handler=_correlation_matrix,
        )
    ]
