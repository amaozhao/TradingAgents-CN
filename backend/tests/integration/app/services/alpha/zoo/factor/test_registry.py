from __future__ import annotations

import pandas as pd

from trader.factors.registry import FactorRegistry


def test_factor_registry_discovers_canonical_factor_ids():
    registry = FactorRegistry.discover()
    ids = set(registry.ids())

    assert "alpha101_001" in ids
    assert "alpha101_101" in ids
    assert "gtja191_001" in ids
    assert "gtja191_191" in ids
    assert "qlib158_beta10" in ids
    assert "qlib158_wvma60" in ids
    assert len([item for item in ids if item.startswith("alpha101_")]) == 101
    assert len([item for item in ids if item.startswith("gtja191_")]) == 191
    assert len([item for item in ids if item.startswith("qlib158_")]) == 154


def test_factor_metadata_and_calculation_contract():
    registry = FactorRegistry.discover()
    factor = registry.get("alpha101_001")

    assert factor.metadata.factor_id == "alpha101_001"
    assert factor.metadata.required_columns

    index = pd.to_datetime(["2026-06-01", "2026-06-02"])
    panel = {
        "close": pd.DataFrame({"600519": [10.0, 11.0]}, index=index),
        "open": pd.DataFrame({"600519": [9.5, 10.5]}, index=index),
        "high": pd.DataFrame({"600519": [10.5, 11.5]}, index=index),
        "low": pd.DataFrame({"600519": [9.0, 10.0]}, index=index),
        "volume": pd.DataFrame({"600519": [100.0, 120.0]}, index=index),
        "amount": pd.DataFrame({"600519": [1000.0, 1320.0]}, index=index),
        "vwap": pd.DataFrame({"600519": [10.0, 11.0]}, index=index),
        "_meta": {"source": "fixture"},
    }

    result = factor.calculate(panel)

    assert list(result.columns) == ["600519"]
    assert result.index.equals(panel["close"].index)
