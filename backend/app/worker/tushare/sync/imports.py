"""
Tushare数据同步服务
负责将Tushare数据同步到PostgreSQL标准化集合
"""

import asyncio
import importlib
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

from trader.flows.providers.china.tushare import TushareProvider

from app.core.config import settings
from app.core.database import get_postgres_db
from app.core.limiter import get_tushare_rate_limiter
from app.db.dual import dual_write_hot_document
from app.services.market.historical import get_historical_data_service
from app.services.market.news import get_news_data_service
from app.services.scheduler import TaskCancelledException, get_utc8_now
from app.services.stocks.service import get_stock_data_service
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# UTC+8 时区
UTC_8 = timezone(timedelta(hours=8))

__all__ = [
    "Any",
    "Dict",
    "List",
    "Optional",
    "TaskCancelledException",
    "TushareProvider",
    "asyncio",
    "cast",
    "datetime",
    "dual_write_hot_document",
    "get_historical_data_service",
    "get_news_data_service",
    "get_postgres_db",
    "get_stock_data_service",
    "get_tushare_rate_limiter",
    "get_utc8_now",
    "importlib",
    "inspect",
    "now_tz",
    "settings",
]
