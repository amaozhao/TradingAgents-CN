"""Compare multiple registered alpha factor outputs."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from trader.factors.base import Panel
from trader.factors.factor_analysis_core import calculate_factor
from trader.factors.registry import FactorRegistry


def compare_factors(
    factor_ids: Iterable[str],
    panel: Panel,
    *,
    registry: FactorRegistry | None = None,
) -> pd.DataFrame:
    """Return per-factor output coverage for quick comparisons."""
    active_registry = registry or FactorRegistry.discover()
    rows = []
    for factor_id in factor_ids:
        result = calculate_factor(factor_id, panel, registry=active_registry)
        rows.append(
            {
                "factor_id": factor_id,
                "rows": len(result.index),
                "columns": len(result.columns),
                "non_null_values": int(result.count().sum()),
            }
        )
    return pd.DataFrame(rows, columns=["factor_id", "rows", "columns", "non_null_values"])
