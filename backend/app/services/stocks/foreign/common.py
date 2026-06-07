"""
港股和美股数据服务
🔥 复用统一数据源管理器（UnifiedStockService）
🔥 按照数据库配置的数据源优先级调用API
🔥 请求去重机制：防止并发请求重复调用API
"""

# ruff: noqa: F401

import asyncio
import importlib
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from app.core.config import settings

# 复用现有缓存系统
from trader.flows.cache import get_cache

# 复用现有数据源提供者
from trader.flows.providers.hk.stock import HKStockProvider

logger = logging.getLogger(__name__)
