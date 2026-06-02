"""Compatibility adapter for legacy ``tradingagents.dataflows.tushare_adapter`` imports."""

from __future__ import annotations

from typing import Any

import pandas as pd

from tradingagents.config.runtime_settings import use_app_cache_enabled
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


class TushareDataAdapter:
    """Small wrapper around the unified Tushare provider.

    Older TradingAgents-CN code used this adapter name and its
    ``_get_realtime_data`` method. New code uses the unified provider directly.
    """

    def __init__(self, enable_cache: bool = True, provider: Any = None) -> None:
        self.enable_cache = enable_cache
        self.provider = provider or get_tushare_provider()

    def _standardize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def _get_realtime_data(self, symbol: str) -> pd.DataFrame:
        if self.enable_cache or use_app_cache_enabled(default=False):
            try:
                from tradingagents.dataflows.app_cache_adapter import get_market_quote_dataframe

                cached = get_market_quote_dataframe(symbol)
                if cached is not None and not cached.empty:
                    return self._standardize_data(cached)
            except Exception:
                pass

        try:
            data = self.provider.get_stock_daily(symbol, None, None)
            if isinstance(data, pd.DataFrame):
                return self._standardize_data(data)
        except Exception:
            pass
        return pd.DataFrame()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.provider, name)


TushareAdapter = TushareDataAdapter


def get_tushare_adapter() -> TushareDataAdapter:
    return TushareDataAdapter()
