#!/usr/bin/env python3
"""
实时新闻数据获取工具
解决新闻滞后性问题
"""

import importlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, cast
from zoneinfo import ZoneInfo

import requests

# 导入日志模块
from app.core.config import settings

from trader.config.runtime import get_timezone_name
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")

__all__ = [
    "Any",
    "List",
    "ZoneInfo",
    "cast",
    "dataclass",
    "datetime",
    "get_timezone_name",
    "importlib",
    "os",
    "requests",
    "settings",
    "time",
    "timedelta",
]
