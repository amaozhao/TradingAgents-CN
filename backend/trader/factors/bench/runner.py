"""Small benchmark runner for alpha factor outputs."""

from __future__ import annotations

from dataclasses import dataclass

from trader.factors.base import Panel
from trader.factors.factor.analysis.core import calculate_factor
from trader.factors.registry import FactorRegistry


@dataclass(frozen=True)
class FactorBenchResult:
    factor_id: str
    rows: int
    columns: int
    non_null_values: int


def run_bench(
    factor_id: str,
    panel: Panel,
    *,
    registry: FactorRegistry | None = None,
) -> FactorBenchResult:
    """Calculate a factor and return a compact output summary."""
    result = calculate_factor(factor_id, panel, registry=registry)
    return FactorBenchResult(
        factor_id=factor_id,
        rows=len(result.index),
        columns=len(result.columns),
        non_null_values=int(result.count().sum()),
    )
