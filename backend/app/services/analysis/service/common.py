"""
股票分析服务
将现有的分析引擎功能包装成API服务
"""

import importlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional, cast

from app.core.database import get_postgres_db, get_redis_client
from app.core.redis import RedisKeys, get_redis_service
from app.db.dual import dual_write_hot_document
from app.db.ids import DocumentId
from app.schemas.analysis import (
    AnalysisParameters,
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
)
from app.schemas.config import UsageRecord
from app.schemas.user import PyDocumentId
from app.services.analysis.simple import (
    create_analysis_config,
    get_provider_by_model_name,
    get_provider_by_model_name_sync,
)
from app.services.progress.redis import RedisProgressTracker
from app.services.queue.service import QueueService
from app.services.usage import UsageStatisticsService


logger = logging.getLogger(__name__)

_trading_agents_logging_initialized = False


def _ensure_trading_agents_logging() -> None:
    global _trading_agents_logging_initialized
    if _trading_agents_logging_initialized:
        return

    init_logging = getattr(
        importlib.import_module("trader.utils.logging.init"), "init_logging"
    )

    init_logging()
    _trading_agents_logging_initialized = True


__all__ = [
    "AnalysisParameters",
    "AnalysisResult",
    "AnalysisStatus",
    "AnalysisTask",
    "Any",
    "Callable",
    "Dict",
    "DocumentId",
    "Optional",
    "PyDocumentId",
    "QueueService",
    "RedisKeys",
    "RedisProgressTracker",
    "UsageRecord",
    "UsageStatisticsService",
    "cast",
    "create_analysis_config",
    "datetime",
    "dual_write_hot_document",
    "get_postgres_db",
    "get_provider_by_model_name",
    "get_provider_by_model_name_sync",
    "get_redis_client",
    "get_redis_service",
    "importlib",
    "json",
    "logger",
    "logging",
    "uuid",
]
