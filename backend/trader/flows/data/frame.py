"""Unified China daily data DataFrame adapter.

This is a narrow compatibility layer for older callers that expect a
DataFrame-returning API. It delegates to the configured CN providers and
standardizes column names without changing the provider implementations.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from trader.flows.akshare import get_akshare_provider
from trader.flows.providers.china.baostock import get_baostock_provider
from trader.flows.sources import get_data_source_manager
from trader.flows.tushare import get_tushare_provider as get_tushare_adapter

_COLUMN_ALIASES = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
    "Amount": "amount",
    "日期": "trade_date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}


def _standardize_daily_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    result = result.rename(
        columns={k: v for k, v in _COLUMN_ALIASES.items() if k in result.columns}
    )
    result.columns = [str(col).lower() for col in result.columns]
    if "date" in result.columns and "trade_date" not in result.columns:
        result = result.rename(columns={"date": "trade_date"})
    return result


def _provider_order() -> Iterable[str]:
    try:
        manager = get_data_source_manager()
        current = getattr(getattr(manager, "current_source", None), "value", None)
        available = list(getattr(manager, "available_sources", []) or [])
    except Exception:
        current = None
        available = []

    seen = set()
    for name in [current, *available, "tushare", "akshare", "baostock"]:
        if name and name not in seen:
            seen.add(name)
            yield name


def _fetch_from_provider(
    provider_name: str, symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    if provider_name == "tushare":
        provider = get_tushare_adapter()
    elif provider_name == "akshare":
        provider = get_akshare_provider()
    elif provider_name == "baostock":
        provider = get_baostock_provider()
    else:
        return pd.DataFrame()

    getter = getattr(provider, "get_stock_data", None)
    if callable(getter):
        result = getter(symbol, start_date, end_date)
        return (
            _standardize_daily_df(result)
            if isinstance(result, pd.DataFrame)
            else pd.DataFrame()
        )

    sync_getter = getattr(provider, "get_stock_data_sync", None)
    if callable(sync_getter):
        result = sync_getter(symbol, start_date, end_date)
        return (
            _standardize_daily_df(result)
            if isinstance(result, pd.DataFrame)
            else pd.DataFrame()
        )

    return pd.DataFrame()


def get_china_daily_df_unified(
    symbol: str, start_date: str, end_date: str
) -> pd.DataFrame:
    for provider_name in _provider_order():
        try:
            df = _fetch_from_provider(provider_name, symbol, start_date, end_date)
        except Exception:
            continue
        if df is not None and not df.empty:
            return df
    return pd.DataFrame()
