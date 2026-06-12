"""
统一的Tushare数据提供器
合并app层和trading_agents层的所有优势功能
"""

import asyncio
import importlib
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from trader.config.providers import get_provider_config

from ...base import BaseStockDataProvider

# 尝试导入tushare
ts: Any = None
try:
    import tushare as _tushare

    ts = _tushare
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [
    "Any",
    "BaseStockDataProvider",
    "Dict",
    "List",
    "Optional",
    "TUSHARE_AVAILABLE",
    "UTC",
    "Union",
    "asyncio",
    "date",
    "datetime",
    "get_provider_config",
    "importlib",
    "logger",
    "logging",
    "pd",
    "timedelta",
    "ts",
]
