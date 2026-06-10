from __future__ import annotations

import importlib
from typing import Any

from .base import BaseStockDataProvider


_EXPORTS = {
    "TushareProvider": (".china", ".china.tushare"),
    "AKShareProvider": (".china", ".china.akshare"),
    "BaoStockProvider": (".china", ".china.baostock"),
    "AKSHARE_AVAILABLE": (".china",),
    "TUSHARE_AVAILABLE": (".china",),
    "BAOSTOCK_AVAILABLE": (".china",),
    "ImprovedHKStockProvider": (".hk",),
    "get_improved_hk_provider": (".hk",),
    "HK_PROVIDER_AVAILABLE": (".hk",),
    "YFinanceUtils": (".us", ".us.yfinance"),
    "OptimizedUSDataProvider": (".us", ".us.optimized"),
    "get_data_in_range": (".us", "..finnhub"),
    "YFINANCE_AVAILABLE": (".us",),
    "OPTIMIZED_US_AVAILABLE": (".us",),
    "FINNHUB_AVAILABLE": (".us",),
}

YahooProvider = None
FinnhubProvider = None


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        for module_path in _EXPORTS[name]:
            try:
                module = importlib.import_module(module_path, __name__)
                value = getattr(module, name)
            except (ImportError, AttributeError):
                continue
            globals()[name] = value
            return value
        return False if name.endswith("_AVAILABLE") else None
    raise AttributeError(name)


__all__ = [
    "BaseStockDataProvider",
    "TushareProvider",
    "AKShareProvider",
    "BaoStockProvider",
    "AKSHARE_AVAILABLE",
    "TUSHARE_AVAILABLE",
    "BAOSTOCK_AVAILABLE",
    "ImprovedHKStockProvider",
    "get_improved_hk_provider",
    "HK_PROVIDER_AVAILABLE",
    "YFinanceUtils",
    "OptimizedUSDataProvider",
    "get_data_in_range",
    "YFINANCE_AVAILABLE",
    "OPTIMIZED_US_AVAILABLE",
    "FINNHUB_AVAILABLE",
    "YahooProvider",
    "FinnhubProvider",
]
