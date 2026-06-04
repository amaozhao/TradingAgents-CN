# ruff: noqa: F401
"""
配置管理服务
"""

import asyncio
import importlib
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.core.database import get_postgres_db
from app.core.unified import unified_config
from app.db.dual import dual_write_hot_document
from app.db.ids import DocumentId
from app.models.config import (
    DatabaseConfig,
    DatabaseType,
    DataSourceConfig,
    DataSourceGrouping,
    DataSourceType,
    LLMConfig,
    LLMProvider,
    MarketCategory,
    ModelCatalog,
    ModelProvider,
    SystemConfig,
)
from app.utils.timezone import now_tz
from trader.llm.clients.providers import canonical_aliases, normalize_provider_key


logger = logging.getLogger(__name__)
