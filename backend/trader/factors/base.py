"""Shared alpha factor contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

Panel = dict[str, pd.DataFrame | dict[str, object]]


@dataclass(frozen=True)
class FactorMetadata:
    """Static description for a registered factor."""

    factor_id: str
    family: str
    number: int
    name: str
    description: str
    required_columns: tuple[str, ...]


class Factor(Protocol):
    """Executable alpha factor contract."""

    metadata: FactorMetadata

    def calculate(self, panel: Panel) -> pd.DataFrame:
        """Return factor values indexed like the input price panel."""
        ...


class GeneratedFactor:
    """Deterministic placeholder factor for a canonical catalog entry.

    The registry establishes stable IDs and calculation contracts first. Formula
    modules can later replace individual generated factors without changing the
    registry or panel loader APIs.
    """

    metadata: FactorMetadata

    def __init__(self, metadata: FactorMetadata) -> None:
        self.metadata = metadata

    def calculate(self, panel: Panel) -> pd.DataFrame:
        required = self.metadata.required_columns
        missing = [column for column in required if column not in panel]
        if missing:
            raise KeyError(
                f"Factor {self.metadata.factor_id} requires missing columns: "
                f"{', '.join(missing)}"
            )

        close = _panel_frame(panel, "close")
        variant = self.metadata.number % 5

        if variant == 1:
            result = close.pct_change(fill_method=None)
        elif variant == 2:
            result = _panel_frame(panel, "open").div(close).sub(1.0)
        elif variant == 3:
            spread = _panel_frame(panel, "high").sub(_panel_frame(panel, "low"))
            result = spread.div(close)
        elif variant == 4:
            result = _panel_frame(panel, "volume").pct_change(fill_method=None)
        else:
            result = _panel_frame(panel, "vwap").div(close).sub(1.0)

        return result.reindex(index=close.index, columns=close.columns)


def _panel_frame(panel: Panel, column: str) -> pd.DataFrame:
    value = panel[column]
    if not isinstance(value, pd.DataFrame):
        raise TypeError(f"Panel column {column!r} must be a pandas DataFrame")
    return value
