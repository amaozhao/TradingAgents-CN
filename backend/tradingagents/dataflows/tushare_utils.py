"""Compatibility helpers for legacy Tushare dataflow imports."""

from tradingagents.dataflows.providers.china.tushare import (
    TUSHARE_AVAILABLE,
    TushareProvider,
    get_tushare_provider,
    ts,
)

__all__ = ["TUSHARE_AVAILABLE", "TushareProvider", "get_tushare_provider", "ts"]
