"""Core helpers for calculating registered alpha factors."""

from __future__ import annotations

import pandas as pd

from trader.factors.base import Panel
from trader.factors.registry import FactorRegistry


def calculate_factor(
    factor_id: str,
    panel: Panel,
    *,
    registry: FactorRegistry | None = None,
) -> pd.DataFrame:
    """Calculate one registered factor against a normalized panel."""
    active_registry = registry or FactorRegistry.discover()
    return active_registry.get(factor_id).calculate(panel)
