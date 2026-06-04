# ruff: noqa: F401,F403,F405,F821
from __future__ import annotations

import asyncio
import atexit
import copy
import importlib
import re
import threading
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Self, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.document import normalize_payload
from app.db.model import (
    AnalysisBatchDocument,
    AnalysisReport,
    AnalysisResultDocument,
    AnalysisTask,
    DatabaseBackupDocument,
    InternalMessageDocument,
    LoginAttemptDocument,
    MarketQuote,
    NotificationDocument,
    OperationLogDocument,
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperTrade,
    PostgresDocument,
    SchedulerExecution,
    SchedulerHistoryDocument,
    SchedulerMetadataDocument,
    SocialMediaMessageDocument,
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SyncStatusDocument,
    SystemConfigDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)
from app.db.session import get_session_factory, init_postgres

_sync_loop: asyncio.AbstractEventLoop | None = None
_sync_loop_thread: threading.Thread | None = None
_sync_loop_lock = threading.Lock()


SPECIALIZED_MODELS: dict[str, Any] = {
    "stock_basic_info": StockBasicInfo,
    "market_quotes": MarketQuote,
    "stock_daily_quotes": StockDailyQuote,
    "stock_financial_data": StockFinancialData,
    "stock_news": StockNewsDocument,
    "analysis_tasks": AnalysisTask,
    "analysis_reports": AnalysisReport,
    "analysis_batches": AnalysisBatchDocument,
    "analysis_results": AnalysisResultDocument,
    "sync_status": SyncStatusDocument,
    "quotes_ingestion_status": SyncStatusDocument,
    "scheduler_executions": SchedulerExecution,
    "scheduler_history": SchedulerHistoryDocument,
    "scheduler_metadata": SchedulerMetadataDocument,
    "user_favorites": UserFavorite,
    "user_tags": UserTag,
    "paper_accounts": PaperAccount,
    "paper_positions": PaperPosition,
    "paper_orders": PaperOrder,
    "paper_trades": PaperTrade,
    "users": UserAccount,
    "users_collection": UserAccount,
    "user_sessions": UserSessionDocument,
    "login_attempts": LoginAttemptDocument,
    "operation_logs": OperationLogDocument,
    "database_backups": DatabaseBackupDocument,
    "notifications": NotificationDocument,
    "token_usage": TokenUsageDocument,
    "internal_messages": InternalMessageDocument,
    "social_media_messages": SocialMediaMessageDocument,
}

CONFIG_COLLECTIONS = {
    "system_configs",
    "llm_providers",
    "model_catalog",
    "market_categories",
    "datasource_groupings",
}
