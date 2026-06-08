from __future__ import annotations

import pandas as pd

from trader.factors.panel_loader import build_panel_from_records


def test_panel_loader_builds_required_columns_and_metadata():
    records = [
        {
            "symbol": "600519",
            "date": "2026-06-01",
            "open": 10.0,
            "high": 12.0,
            "low": 9.5,
            "close": 11.0,
            "volume": 2.0,
            "amount": 22.0,
        },
        {
            "symbol": "600519",
            "date": "2026-06-02",
            "open": 11.0,
            "high": 13.0,
            "low": 10.5,
            "close": 12.0,
            "volume": 3.0,
            "amount": 36.0,
        },
        {
            "symbol": "000001",
            "date": "2026-06-01",
            "open": 5.0,
            "high": 6.0,
            "low": 4.5,
            "close": 5.5,
            "volume": 4.0,
            "amount": 22.0,
        },
    ]
    dates = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"])

    panel = build_panel_from_records(
        records,
        symbols=["600519", "000001", "300750"],
        dates=dates,
        source="fixture",
        volume_unit="lots",
        amount_unit="thousand_yuan",
        adjusted_price="qfq",
        universe_source="test",
    )

    for column in ["open", "high", "low", "close", "volume", "amount", "vwap"]:
        assert column in panel
        assert list(panel[column].columns) == ["600519", "000001", "300750"]

    assert panel["_meta"]["missing_symbols"] == ["300750"]
    assert panel["_meta"]["source_units"]["volume"] == "lots"
    assert panel["_meta"]["source_units"]["amount"] == "thousand_yuan"
    assert panel["_meta"]["normalized_units"]["volume"] == "shares"
    assert panel["_meta"]["normalized_units"]["amount"] == "yuan"
    assert panel["_meta"]["adjusted_price"] == "qfq"

    # amount=22 thousand_yuan and volume=2 lots -> 22000 yuan / 200 shares = 110
    assert panel["vwap"].loc[pd.Timestamp("2026-06-01"), "600519"] == 110.0
    assert pd.isna(panel["close"].loc[pd.Timestamp("2026-06-03"), "600519"])
