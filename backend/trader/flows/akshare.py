"""Compatibility helpers for legacy AKShare dataflow imports."""

import asyncio
from typing import Optional

import pandas as pd

from trader.flows.providers.china.akshare import (
    AKShareProvider,
    get_akshare_provider,
)


def get_stock_news_em(symbol: str, limit: int = 20) -> pd.DataFrame:
    """Return Eastmoney/AKShare stock news as a DataFrame.

    Legacy callers patch this function directly. Prefer the provider's sync
    path so tests and non-async scripts can call it safely.
    """
    provider = get_akshare_provider()
    if hasattr(provider, "get_stock_news_sync"):
        result = provider.get_stock_news_sync(symbol=symbol, limit=limit)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    try:
        result = asyncio.run(provider.get_stock_news(symbol=symbol, limit=limit))
    except RuntimeError:
        return pd.DataFrame()
    return pd.DataFrame(result or [])


__all__ = ["AKShareProvider", "get_akshare_provider", "get_stock_news_em"]
