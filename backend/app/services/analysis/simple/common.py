# ruff: noqa: F401
"""
简化的股票分析服务
直接调用现有的 TradingAgents 分析功能
"""

import asyncio
import importlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from app.core.config import settings
from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.db.ids import DocumentId
from app.schemas.analysis import (
    AnalysisParameters,
    AnalysisStatus,
    SingleAnalysisRequest,
)
from app.schemas.notification import NotificationCreate
from app.schemas.user import PyDocumentId
from app.services.config import ConfigService
from app.services.memory import TaskStatus, get_memory_state_manager
from app.services.progress.log import (
    register_analysis_tracker,
    unregister_analysis_tracker,
)
from app.services.progress.redis import RedisProgressTracker, get_progress_by_id

_trading_agents_logging_initialized = False
_data_source_manager = None

logger = logging.getLogger("app.services.analysis.simple")

config_service = ConfigService()
