"""Canonical alpha factor registry."""

from __future__ import annotations

from collections.abc import Iterable

from trader.factors.base import Factor, FactorMetadata, GeneratedFactor

_FACTOR_FAMILIES: tuple[tuple[str, int, str], ...] = (
    ("alpha101", 101, "Alpha101"),
    ("gtja191", 191, "GTJA191"),
    ("qlib158", 158, "Qlib158"),
)

_DEFAULT_REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "vwap",
)


class FactorRegistry:
    """In-memory registry for executable alpha factors."""

    def __init__(self, factors: Iterable[Factor]) -> None:
        self._factors = {factor.metadata.factor_id: factor for factor in factors}

    @classmethod
    def discover(cls) -> "FactorRegistry":
        """Build the canonical generated factor catalog."""
        factors: list[Factor] = []
        for family, count, display_name in _FACTOR_FAMILIES:
            for number in range(1, count + 1):
                factor_id = f"{family}_{number:03d}"
                factors.append(
                    GeneratedFactor(
                        FactorMetadata(
                            factor_id=factor_id,
                            family=family,
                            number=number,
                            name=f"{display_name} #{number:03d}",
                            description=(
                                f"Deterministic baseline implementation for "
                                f"{display_name} factor #{number:03d}."
                            ),
                            required_columns=_DEFAULT_REQUIRED_COLUMNS,
                        )
                    )
                )
        return cls(factors)

    def ids(self) -> list[str]:
        """Return registered factor IDs in stable sorted order."""
        return sorted(self._factors)

    def get(self, factor_id: str) -> Factor:
        """Return one registered factor by canonical ID."""
        try:
            return self._factors[factor_id]
        except KeyError as exc:
            raise KeyError(f"Unknown factor ID: {factor_id}") from exc

    def all(self) -> list[Factor]:
        """Return all factors in stable ID order."""
        return [self._factors[factor_id] for factor_id in self.ids()]
