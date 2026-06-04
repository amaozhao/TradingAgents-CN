# ruff: noqa: F401,F403,F405,F821
#!/usr/bin/env python3
"""
优化的A股数据获取工具
集成缓存策略和Tushare数据接口，提高数据获取效率
"""

import importlib
import random
import time
from datetime import datetime
from typing import Any, Dict, Optional, cast
from zoneinfo import ZoneInfo

from trader.config.manager import config_manager
from trader.config.runtime import get_float, get_timezone_name
from trader.flows.cache.postgres import get_postgres_cache_adapter
from trader.utils.logging.manager import get_logger

from ..cache import get_cache

logger = get_logger("agents")
