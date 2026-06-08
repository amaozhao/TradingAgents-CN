"""Build normalized wide price panels for alpha factor calculations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

REQUIRED_PANEL_COLUMNS = ("open", "high", "low", "close", "volume", "amount", "vwap")

_VOLUME_MULTIPLIERS = {
    "shares": 1.0,
    "share": 1.0,
    "lots": 100.0,
    "lot": 100.0,
}

_AMOUNT_MULTIPLIERS = {
    "yuan": 1.0,
    "cny": 1.0,
    "thousand_yuan": 1000.0,
    "thousand_cny": 1000.0,
}


def build_panel_from_records(
    records: Iterable[Mapping[str, Any]],
    *,
    symbols: Sequence[str],
    dates: Sequence[Any],
    source: str,
    volume_unit: str,
    amount_unit: str,
    adjusted_price: str | None = None,
    universe_source: str | None = None,
) -> dict[str, pd.DataFrame | dict[str, object]]:
    """Convert row records into normalized factor panel frames.

    Input volume and amount units are preserved in metadata and normalized to
    shares/yuan before vwap calculation.
    """
    symbol_list = list(symbols)
    date_index = pd.DatetimeIndex(pd.to_datetime(list(dates))).sort_values()
    raw = pd.DataFrame(list(records))

    panel: dict[str, pd.DataFrame | dict[str, object]] = {}
    for column in ("open", "high", "low", "close"):
        panel[column] = _wide_frame(raw, column, date_index, symbol_list)

    volume_multiplier = _unit_multiplier(volume_unit, _VOLUME_MULTIPLIERS, "volume")
    amount_multiplier = _unit_multiplier(amount_unit, _AMOUNT_MULTIPLIERS, "amount")
    volume = _wide_frame(raw, "volume", date_index, symbol_list) * volume_multiplier
    amount = _wide_frame(raw, "amount", date_index, symbol_list) * amount_multiplier
    panel["volume"] = volume
    panel["amount"] = amount
    panel["vwap"] = amount.div(volume.mask(volume == 0))

    present_symbols = set()
    if not raw.empty and "symbol" in raw:
        present_symbols = {str(symbol) for symbol in raw["symbol"].dropna().unique()}
    missing_symbols = [symbol for symbol in symbol_list if symbol not in present_symbols]

    panel["_meta"] = {
        "source": source,
        "adjusted_price": adjusted_price,
        "trading_calendar": [date.strftime("%Y-%m-%d") for date in date_index],
        "source_units": {"volume": volume_unit, "amount": amount_unit},
        "normalized_units": {"volume": "shares", "amount": "yuan"},
        "universe_source": universe_source,
        "missing_symbols": missing_symbols,
        "sparse_dates": _sparse_dates(panel["close"], missing_symbols),
        "suspended_dates": {},
    }
    return panel


def _wide_frame(
    raw: pd.DataFrame,
    column: str,
    date_index: pd.DatetimeIndex,
    symbols: Sequence[str],
) -> pd.DataFrame:
    empty = pd.DataFrame(index=date_index, columns=symbols, dtype=float)
    if raw.empty or column not in raw or "symbol" not in raw or "date" not in raw:
        return empty

    data = raw[["symbol", "date", column]].copy()
    data["symbol"] = data["symbol"].astype(str)
    data["date"] = pd.to_datetime(data["date"])
    data[column] = pd.to_numeric(data[column], errors="coerce")
    wide = data.pivot_table(
        index="date",
        columns="symbol",
        values=column,
        aggfunc="last",
    )
    return wide.reindex(index=date_index, columns=symbols).astype(float)


def _unit_multiplier(
    unit: str,
    multipliers: Mapping[str, float],
    value_name: str,
) -> float:
    normalized = unit.lower()
    try:
        return multipliers[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(multipliers))
        raise ValueError(
            f"Unsupported {value_name} unit {unit!r}; supported units: {supported}"
        ) from exc


def _sparse_dates(
    close: pd.DataFrame | dict[str, object],
    missing_symbols: Sequence[str],
) -> dict[str, list[str]]:
    if not isinstance(close, pd.DataFrame):
        return {}

    missing_set = set(missing_symbols)
    sparse: dict[str, list[str]] = {}
    for symbol in close.columns:
        if symbol in missing_set:
            continue
        dates = close.index[close[symbol].isna()]
        if len(dates) > 0:
            sparse[str(symbol)] = [date.strftime("%Y-%m-%d") for date in dates]
    return sparse
