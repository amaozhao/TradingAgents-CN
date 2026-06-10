"""Worker package for analysis and related background jobs."""

from __future__ import annotations

import importlib
from typing import Any


_LAZY_MODULES = {
    "akshare_sync_service": ".akshare.sync",
    "baostock_init_service": ".baostock.init",
    "baostock_sync_service": ".baostock.sync",
    "example_sdk_sync_service": ".examples",
    "hk_data_service": ".hk.data",
    "hk_sync_service": ".hk.sync",
    "tushare_sync_service": ".tushare.sync",
    "us_data_service": ".us.data",
    "us_sync_service": ".us.sync",
}


def __getattr__(name: str) -> Any:
    try:
        module_path = _LAZY_MODULES[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = importlib.import_module(module_path, __name__)
    globals()[name] = module
    return module

__all__ = [
    "akshare_sync_service",
    "baostock_init_service",
    "baostock_sync_service",
    "example_sdk_sync_service",
    "hk_data_service",
    "hk_sync_service",
    "tushare_sync_service",
    "us_data_service",
    "us_sync_service",
]
