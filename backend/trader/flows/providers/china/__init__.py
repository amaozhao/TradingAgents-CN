from __future__ import annotations

import importlib
import sys
from typing import Any


_EXPORTS = {
    "AKShareProvider": ".akshare",
    "TushareProvider": ".tushare",
    "BaoStockProvider": ".baostock",
    "BaostockProvider": ".baostock",
    "get_fundamentals_snapshot": ".fundamentals",
}

_AVAILABILITY = {
    "AKSHARE_AVAILABLE": "AKShareProvider",
    "TUSHARE_AVAILABLE": "TushareProvider",
    "BAOSTOCK_AVAILABLE": "BaoStockProvider",
    "FUNDAMENTALS_SNAPSHOT_AVAILABLE": "get_fundamentals_snapshot",
}


def __getattr__(name: str) -> Any:
    if name in _AVAILABILITY:
        return getattr(sys.modules[__name__], _AVAILABILITY[name]) is not None

    if name in _EXPORTS:
        try:
            module = importlib.import_module(_EXPORTS[name], __name__)
            value = getattr(module, "BaoStockProvider" if name == "BaostockProvider" else name)
        except (ImportError, AttributeError):
            value = None
        globals()[name] = value
        return value

    raise AttributeError(name)


__all__ = [
    "AKShareProvider",
    "AKSHARE_AVAILABLE",
    "TushareProvider",
    "TUSHARE_AVAILABLE",
    "BaoStockProvider",
    "BaostockProvider",
    "BAOSTOCK_AVAILABLE",
    "get_fundamentals_snapshot",
    "FUNDAMENTALS_SNAPSHOT_AVAILABLE",
]
