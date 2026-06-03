"""Compatibility helpers for legacy Tushare dataflow imports."""

from trader.flows.providers.china.tushare import (
    TUSHARE_AVAILABLE,
    TushareProvider,
    get_tushare_provider,
    ts,
)

__all__ = ["TUSHARE_AVAILABLE", "TushareProvider", "get_tushare_provider", "ts"]
