#!/usr/bin/env python3
"""
BaoStock统一数据提供器
实现BaseStockDataProvider接口，提供标准化的BaoStock数据访问
"""

import asyncio
import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from app.core.baostock.runtime import run_baostock_session, run_baostock_session_async

from ...base import BaseStockDataProvider

logger = logging.getLogger(__name__)

__all__ = [
    "Any",
    "BaseStockDataProvider",
    "Dict",
    "List",
    "Optional",
    "asyncio",
    "cast",
    "datetime",
    "importlib",
    "logger",
    "logging",
    "pd",
    "run_baostock_session",
    "run_baostock_session_async",
    "timedelta",
    "timezone",
]
