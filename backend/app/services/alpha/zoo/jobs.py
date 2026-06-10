from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from app.services.research.agent.artifacts import ResearchArtifactService
from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.jobs import ResearchJobService
from trader.factors.bench.runner import run_bench
from trader.factors.compare.runner import compare_factors
from trader.factors.panel.loader import build_panel_from_records
from trader.factors.registry import FactorRegistry


class AlphaZooJobService:
    def __init__(
        self,
        *,
        job_service: ResearchJobService | None = None,
        artifact_service: ResearchArtifactService | None = None,
        registry: FactorRegistry | None = None,
    ) -> None:
        self.job_service = job_service or ResearchJobService()
        self.artifact_service = artifact_service or ResearchArtifactService()
        self.registry = registry or FactorRegistry.discover()

    async def create_bench_job(
        self,
        *,
        principal: ResearchPrincipal,
        alpha_id: str,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        self.registry.get(alpha_id)
        clean_symbols = _symbols_or_default(symbols)
        payload = {
            "alpha_id": alpha_id,
            "symbols": clean_symbols,
            "start_date": start_date,
            "end_date": end_date,
        }
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="alpha_bench",
            resource_id=alpha_id,
            payload=payload,
        )
        await self.job_service.mark_running(job["job_id"])
        panel = _build_synthetic_panel(clean_symbols, start_date, end_date)
        bench = run_bench(alpha_id, panel, registry=self.registry)
        artifact_payload = {
            "kind": "alpha_bench",
            "alpha_id": alpha_id,
            "symbols": clean_symbols,
            "summary": bench.__dict__,
            "classification": _classify_coverage(bench.non_null_values),
        }
        artifact = await self.artifact_service.create_artifact(
            session_id=job["job_id"],
            user_id=principal.user_id,
            artifact_type="alpha_bench",
            payload=artifact_payload,
        )
        result = {
            **artifact_payload,
            "artifact_id": artifact["artifact_id"],
        }
        await self.job_service.mark_completed(job["job_id"], result)
        completed = await self.job_service.get(job["job_id"], principal.user_id)
        return completed or {**job, "status": "completed", "result": result}

    async def create_compare_job(
        self,
        *,
        principal: ResearchPrincipal,
        alpha_ids: list[str],
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        clean_alpha_ids = [alpha_id for alpha_id in alpha_ids if alpha_id]
        if not clean_alpha_ids:
            raise KeyError("At least one alpha ID is required")
        for alpha_id in clean_alpha_ids:
            self.registry.get(alpha_id)
        clean_symbols = _symbols_or_default(symbols)
        payload = {
            "alpha_ids": clean_alpha_ids,
            "symbols": clean_symbols,
            "start_date": start_date,
            "end_date": end_date,
        }
        job = await self.job_service.enqueue(
            principal=principal,
            task_type="alpha_compare",
            resource_id=",".join(clean_alpha_ids),
            payload=payload,
        )
        await self.job_service.mark_running(job["job_id"])
        panel = _build_synthetic_panel(clean_symbols, start_date, end_date)
        comparison = compare_factors(clean_alpha_ids, panel, registry=self.registry)
        rows = comparison.to_dict(orient="records")
        artifact_payload = {
            "kind": "alpha_compare",
            "alpha_ids": clean_alpha_ids,
            "symbols": clean_symbols,
            "rows": rows,
        }
        artifact = await self.artifact_service.create_artifact(
            session_id=job["job_id"],
            user_id=principal.user_id,
            artifact_type="alpha_compare",
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


def _symbols_or_default(symbols: list[str]) -> list[str]:
    clean = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
    return clean or ["600519"]


def _build_synthetic_panel(
    symbols: list[str],
    start_date: str | None,
    end_date: str | None,
) -> dict[str, pd.DataFrame | dict[str, object]]:
    start = pd.Timestamp(start_date or date.today().isoformat())
    if end_date:
        end = pd.Timestamp(end_date)
        dates = pd.date_range(start, end, freq="D")
    else:
        dates = pd.date_range(start, periods=3, freq="D")
    if len(dates) == 0:
        dates = pd.date_range(start, periods=1, freq="D")

    records: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(symbols):
        base = 10.0 + symbol_index
        for offset, current_date in enumerate(dates):
            close = base + offset
            volume = float(1000 + offset * 10 + symbol_index)
            records.append(
                {
                    "symbol": symbol,
                    "date": current_date.strftime("%Y-%m-%d"),
                    "open": close - 0.2,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": volume,
                    "amount": close * volume,
                }
            )
    return build_panel_from_records(
        records,
        symbols=symbols,
        dates=dates,
        source="synthetic",
        volume_unit="shares",
        amount_unit="yuan",
        adjusted_price="none",
        universe_source="explicit",
    )


def _classify_coverage(non_null_values: int) -> str:
    if non_null_values <= 0:
        return "dead"
    return "alive"
