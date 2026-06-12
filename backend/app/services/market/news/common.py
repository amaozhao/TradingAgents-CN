"""
新闻数据服务
提供统一的新闻数据存储、查询和管理功能
"""

import importlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, cast

from app.core.config import settings
from app.core.database import get_database
from app.db.store import BulkWriteError, ReplaceOne
from app.db.dual import dual_write_hot_documents


logger = logging.getLogger(__name__)

__all__ = [
    "Any",
    "BulkWriteError",
    "Dict",
    "List",
    "Optional",
    "ReplaceOne",
    "Union",
    "cast",
    "dataclass",
    "datetime",
    "dual_write_hot_documents",
    "field",
    "get_database",
    "importlib",
    "settings",
    "timedelta",
]
