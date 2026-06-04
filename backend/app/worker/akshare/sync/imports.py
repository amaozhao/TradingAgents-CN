# ruff: noqa: F401,F403,F405,F821
"""
AKShare数据同步服务
基于AKShare提供器的统一数据同步方案
"""

import asyncio
import importlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.services.market.historical import get_historical_data_service
from app.services.market.news import get_news_data_service
from trader.flows.providers.china.akshare import get_akshare_provider

logger = logging.getLogger(__name__)
