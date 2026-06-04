from __future__ import annotations

import asyncio
import threading
from typing import Any

from app.models.table import (
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
    SchedulerExecution,
    SchedulerHistoryDocument,
    SchedulerMetadataDocument,
    SocialMediaMessageDocument,
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SyncStatusDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)

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
