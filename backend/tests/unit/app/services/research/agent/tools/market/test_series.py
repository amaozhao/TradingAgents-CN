import pytest
import pandas as pd

from app.services.research.agent.tools.market import series


def _row(source: str = "okx") -> dict[str, object]:
    return {
        "symbol": "BTC-USDT",
        "trade_date": "2026-06-01",
        "open": 67000.0,
        "high": 68000.0,
        "low": 66000.0,
        "close": 67500.0,
        "volume": 100.0,
        "data_source": source,
    }


@pytest.mark.unit
def test_crypto_symbol_conversions_prefer_exchange_pairs() -> None:
    assert series.normalize_symbol("BTCUSDT") == "BTC-USDT"
    assert series._to_okx_symbol("BTC-USD") == "BTC-USDT"
    assert series._to_okx_symbol("ETH/USDT") == "ETH-USDT"
    assert series._to_ccxt_symbol("BTC-USD") == "BTC/USDT"
    assert series._to_yfinance_symbol("BTC-USDT") == "BTC-USD"


@pytest.mark.unit
def test_frame_to_rows_preserves_trade_date_column() -> None:
    frame = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2026-06-01"),
                "open": "67000",
                "high": "68000",
                "low": "66000",
                "close": "67500",
                "volume": "100",
            }
        ]
    )

    rows = series._frame_to_rows(frame, symbol="BTC-USDT", source="okx")

    assert rows[0]["trade_date"] == "2026-06-01"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crypto_provider_prefers_okx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def okx(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        return [_row("okx")]

    async def unexpected(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        raise AssertionError("fallback should not run after OKX succeeds")

    monkeypatch.setattr(series, "_fetch_okx", okx)
    monkeypatch.setattr(series, "_fetch_ccxt", unexpected)
    monkeypatch.setattr(series, "_fetch_yfinance", unexpected)

    rows, source, diagnostics = await series._load_from_provider(
        "BTC-USDT",
        start_date="2026-06-01",
        end_date="2026-06-02",
    )

    assert source == "okx"
    assert rows == [_row("okx")]
    assert [item["source"] for item in diagnostics] == ["okx"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crypto_provider_falls_back_to_ccxt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        return []

    async def ccxt(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        return [_row("ccxt")]

    async def unexpected(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        raise AssertionError("yfinance should not run after CCXT succeeds")

    monkeypatch.setattr(series, "_fetch_okx", empty)
    monkeypatch.setattr(series, "_fetch_ccxt", ccxt)
    monkeypatch.setattr(series, "_fetch_yfinance", unexpected)

    rows, source, diagnostics = await series._load_from_provider(
        "BTC-USDT",
        start_date="2026-06-01",
        end_date="2026-06-02",
    )

    assert source == "ccxt"
    assert rows == [_row("ccxt")]
    assert [item["source"] for item in diagnostics] == ["okx", "ccxt"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crypto_provider_uses_yfinance_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        return []

    async def yfinance(
        symbol: str, start_date: str, end_date: str
    ) -> list[dict[str, object]]:
        return [_row("yfinance")]

    monkeypatch.setattr(series, "_fetch_okx", empty)
    monkeypatch.setattr(series, "_fetch_ccxt", empty)
    monkeypatch.setattr(series, "_fetch_yfinance", yfinance)

    rows, source, diagnostics = await series._load_from_provider(
        "BTC-USDT",
        start_date="2026-06-01",
        end_date="2026-06-02",
    )

    assert source == "yfinance"
    assert rows == [_row("yfinance")]
    assert [item["source"] for item in diagnostics] == ["okx", "ccxt", "yfinance"]
