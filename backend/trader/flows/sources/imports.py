# ruff: noqa: F401,F403,F405,F821
#!/usr/bin/env python3
"""
数据源管理器
统一管理中国股票数据源的选择和切换，支持Tushare、AKShare、BaoStock等
"""

import importlib
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

import numpy as np
import pandas as pd

from trader.config.databases import get_database_manager
from trader.constants import DataSourceCode
from trader.utils.logging.init import setup_dataflow_logging
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")
warnings.filterwarnings("ignore")

logger = setup_dataflow_logging()


class ChinaDataSource(str, Enum):
    """中国市场数据源。"""

    POSTGRES = DataSourceCode.POSTGRES.value
    TUSHARE = DataSourceCode.TUSHARE.value
    AKSHARE = DataSourceCode.AKSHARE.value
    BAOSTOCK = DataSourceCode.BAOSTOCK.value


class USDataSource(str, Enum):
    """美国市场数据源。"""

    POSTGRES = DataSourceCode.POSTGRES.value
    YFINANCE = DataSourceCode.YFINANCE.value
    ALPHA_VANTAGE = DataSourceCode.ALPHA_VANTAGE.value
    FINNHUB = DataSourceCode.FINNHUB.value


_T = TypeVar("_T")


def run_async_provider_call(coro_factory: Callable[[], Any]) -> _T:
    """Run an async provider call from sync data-source code."""

    asyncio = importlib.import_module("asyncio")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return cast(_T, asyncio.run(coro_factory()))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coro_factory()))
        return cast(_T, future.result())
