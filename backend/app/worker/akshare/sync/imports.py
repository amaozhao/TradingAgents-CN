"""
AKShare数据同步服务
基于AKShare提供器的统一数据同步方案
"""

import asyncio
import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

from trader.flows.providers.china.akshare import get_akshare_provider

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.services.market.historical import get_historical_data_service
from app.services.market.news import get_news_data_service

logger = logging.getLogger(__name__)


def utcnow_naive() -> datetime:
    """Return a naive UTC datetime for legacy document fields."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

__all__ = [
    "Any",
    "Dict",
    "List",
    "Optional",
    "asyncio",
    "cast",
    "dual_write_hot_document",
    "get_akshare_provider",
    "get_historical_data_service",
    "get_news_data_service",
    "get_postgres_db",
    "importlib",
    "timedelta",
]
