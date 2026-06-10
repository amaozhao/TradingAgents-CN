from __future__ import annotations

import os
from typing import Any

import pytest

from app.services.research.agent.tools.market import series as market_series


def test_cn_market_no_proxy_preserves_existing_entries(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.delenv("no_proxy", raising=False)

    entries = market_series.ensure_cn_market_no_proxy()

    assert entries[:2] == ["localhost", "127.0.0.1"]
    assert "eastmoney.com" in entries
    assert "api.tushare.pro" in entries
    assert "baostock.com" in entries
    assert os.environ["NO_PROXY"] == os.environ["no_proxy"]


@pytest.mark.asyncio
async def test_load_price_series_exposes_degraded_diagnostics(monkeypatch):
    async def fake_load_from_postgres(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def fake_load_from_provider(*_args: Any, **_kwargs: Any):
        return (
            [],
            None,
            [
                {"source": "akshare", "status": "empty", "message": "akshare returned no usable rows."},
                {"source": "baostock", "status": "timeout", "message": "baostock request exceeded 8s timeout."},
            ],
        )

    monkeypatch.setattr(market_series, "_load_from_postgres", fake_load_from_postgres)
    monkeypatch.setattr(market_series, "_load_from_provider", fake_load_from_provider)

    result = await market_series.load_price_series(
        ["600519"],
        start_date="2026-01-01",
        end_date="2026-06-01",
    )

    snapshot = result["600519"]
    assert snapshot["status"] == "degraded"
    assert "A 股行情数据未取得可用价格序列" in snapshot["reason"]
    assert snapshot["source_diagnostics"][0]["source"] == "akshare"
    assert snapshot["source_diagnostics"][1]["status"] == "timeout"


@pytest.mark.asyncio
async def test_lookup_market_snapshot_promotes_history_reason(monkeypatch):
    async def fake_basic_info(_symbol: str):
        return None

    async def fake_quote(_symbol: str):
        return None

    async def fake_load_price_series(*_args: Any, **_kwargs: Any):
        return {
            "600519": {
                "prices": [],
                "status": "degraded",
                "reason": "mock provider reason",
                "source_diagnostics": [{"source": "akshare", "status": "empty"}],
            }
        }

    monkeypatch.setattr(market_series, "_get_basic_info", fake_basic_info)
    monkeypatch.setattr(market_series, "_get_quote", fake_quote)
    monkeypatch.setattr(market_series, "load_price_series", fake_load_price_series)

    result = await market_series.lookup_market_snapshot("600519")

    assert result["status"] == "degraded"
    assert result["reason"] == "mock provider reason"
    assert result["source_diagnostics"] == [{"source": "akshare", "status": "empty"}]
