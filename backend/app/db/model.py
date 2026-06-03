from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JsonbLegacyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legacy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StockBasicInfo(JsonbLegacyMixin, Base):
    __tablename__ = "stock_basic_info"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_stock_basic_info_legacy_id"),
        UniqueConstraint("code", "source", name="uq_stock_basic_info_code_source"),
        Index("ix_stock_basic_info_industry", "industry"),
        Index("ix_stock_basic_info_total_mv", "total_mv"),
        Index("ix_stock_basic_info_pe", "pe"),
        Index("ix_stock_basic_info_pb", "pb"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    name: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    area: Mapped[str | None] = mapped_column(String(128))
    market: Mapped[str | None] = mapped_column(String(32))
    list_date: Mapped[date | None] = mapped_column(Date)
    total_mv: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    circ_mv: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    pe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pb: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pb_mrq: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))


class MarketQuote(JsonbLegacyMixin, Base):
    __tablename__ = "market_quotes"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_market_quotes_legacy_id"),
        UniqueConstraint("code", "source", name="uq_market_quotes_code_source"),
        Index("ix_market_quotes_pct_chg", "pct_chg"),
        Index("ix_market_quotes_amount", "amount"),
        Index("ix_market_quotes_updated_at", "updated_at"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    trade_date: Mapped[date | None] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))


class StockDailyQuote(JsonbLegacyMixin, Base):
    __tablename__ = "stock_daily_quotes"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_stock_daily_quotes_legacy_id"),
        UniqueConstraint("symbol", "trade_date", "data_source", "period", name="uq_stock_daily_quotes_symbol_date_source_period"),
        Index("ix_stock_daily_quotes_symbol_date", "symbol", "trade_date"),
        Index("ix_stock_daily_quotes_trade_date", "trade_date"),
        Index("ix_stock_daily_quotes_market_source", "market", "data_source"),
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
    full_symbol: Mapped[str | None] = mapped_column(String(32))
    market: Mapped[str | None] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False, default="daily")
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pre_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    change: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pct_chg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class StockFinancialData(JsonbLegacyMixin, Base):
    __tablename__ = "stock_financial_data"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_stock_financial_data_legacy_id"),
        UniqueConstraint("code", "data_source", "report_period", name="uq_stock_financial_data_code_source_period"),
        Index("ix_stock_financial_data_report_period", "report_period"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    report_period: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    roe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    roa: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    netprofit_margin: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))


class StockNewsDocument(JsonbLegacyMixin, Base):
    __tablename__ = "stock_news"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_stock_news_legacy_id"),
        Index("ix_stock_news_symbol_publish_time", "symbol", "publish_time"),
        Index("ix_stock_news_source_category", "data_source", "category"),
        Index("ix_stock_news_sentiment_importance", "sentiment", "importance"),
    )

    symbol: Mapped[str | None] = mapped_column(String(32))
    market: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    sentiment: Mapped[str | None] = mapped_column(String(32))
    importance: Mapped[str | None] = mapped_column(String(32))
    publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AnalysisTask(JsonbLegacyMixin, Base):
    __tablename__ = "analysis_tasks"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_analysis_tasks_legacy_id"),
        UniqueConstraint("task_id", name="uq_analysis_tasks_task_id"),
        Index("ix_analysis_tasks_user_status_created", "user_id", "status", "created_at"),
        Index("ix_analysis_tasks_task_id", "task_id"),
    )

    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128))
    stock_symbol: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[int | None] = mapped_column(Integer)


class AnalysisReport(JsonbLegacyMixin, Base):
    __tablename__ = "analysis_reports"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_analysis_reports_legacy_id"),
        UniqueConstraint("analysis_id", name="uq_analysis_reports_analysis_id"),
        Index("ix_analysis_reports_task_id", "task_id"),
        Index("ix_analysis_reports_user_symbol_date", "user_id", "stock_symbol", "analysis_date"),
        Index("ix_analysis_reports_analysis_id", "analysis_id"),
    )

    analysis_id: Mapped[str] = mapped_column(String(160), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(128))
    stock_symbol: Mapped[str | None] = mapped_column(String(32))
    analysis_date: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str | None] = mapped_column(Text)


class AnalysisBatchDocument(JsonbLegacyMixin, Base):
    __tablename__ = "analysis_batches"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_analysis_batches_legacy_id"),
        UniqueConstraint("batch_id", name="uq_analysis_batches_batch_id"),
        Index("ix_analysis_batches_user_status_created", "user_id", "status", "created_at"),
    )

    batch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str | None] = mapped_column(String(32))
    total_tasks: Mapped[int | None] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AnalysisResultDocument(JsonbLegacyMixin, Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_analysis_legacy_id"),
        Index("ix_analysis_task_user_created", "task_id", "user_id", "created_at"),
    )

    task_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(128))
    stock_symbol: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SystemConfigDocument(JsonbLegacyMixin, Base):
    __tablename__ = "system_config_documents"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_system_config_documents_legacy_id"),
        UniqueConstraint("config_key", name="uq_system_config_documents_config_key"),
        Index("ix_system_config_documents_config_type", "config_type"),
    )

    config_key: Mapped[str] = mapped_column(String(160), nullable=False)
    config_type: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool | None] = mapped_column(Boolean)


class SyncStatusDocument(JsonbLegacyMixin, Base):
    __tablename__ = "sync_status"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_sync_status_legacy_id"),
        UniqueConstraint("job", name="uq_sync_status_job"),
        Index("ix_sync_status_status_finished", "status", "finished_at"),
    )

    job: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str | None] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))


class SchedulerExecution(JsonbLegacyMixin, Base):
    __tablename__ = "scheduler_executions"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_scheduler_executions_legacy_id"),
        Index("ix_scheduler_executions_job_status_timestamp", "job_id", "status", "timestamp"),
    )

    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[int | None] = mapped_column(Integer)
    progress_message: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool | None] = mapped_column(Boolean)


class SchedulerHistoryDocument(JsonbLegacyMixin, Base):
    __tablename__ = "scheduler_history"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_scheduler_history_legacy_id"),
        Index("ix_scheduler_history_job_status_timestamp", "job_id", "status", "timestamp"),
    )

    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SchedulerMetadataDocument(JsonbLegacyMixin, Base):
    __tablename__ = "scheduler_metadata"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_scheduler_metadata_legacy_id"),
        UniqueConstraint("job_id", name="uq_scheduler_metadata_job_id"),
    )

    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserFavorite(JsonbLegacyMixin, Base):
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_user_favorites_legacy_id"),
        UniqueConstraint("user_id", "stock_code", name="uq_user_favorites_user_stock"),
        Index("ix_user_favorites_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(32), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(128))
    market: Mapped[str | None] = mapped_column(String(32))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserTag(JsonbLegacyMixin, Base):
    __tablename__ = "user_tags"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_user_tags_legacy_id"),
        UniqueConstraint("user_id", "name", name="uq_user_tags_user_name"),
        Index("ix_user_tags_user_sort", "user_id", "sort_order"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tag_id: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str | None] = mapped_column(String(32))
    sort_order: Mapped[int | None] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PaperAccount(JsonbLegacyMixin, Base):
    __tablename__ = "paper_accounts"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_paper_accounts_legacy_id"),
        UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PaperPosition(JsonbLegacyMixin, Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_paper_positions_legacy_id"),
        UniqueConstraint("user_id", "code", name="uq_paper_positions_user_code"),
        Index("ix_paper_positions_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str | None] = mapped_column(String(16))
    currency: Mapped[str | None] = mapped_column(String(8))
    quantity: Mapped[int | None] = mapped_column(Integer)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PaperOrder(JsonbLegacyMixin, Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_paper_orders_legacy_id"),
        Index("ix_paper_orders_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
    side: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str | None] = mapped_column(String(32))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PaperTrade(JsonbLegacyMixin, Base):
    __tablename__ = "paper_trades"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_paper_trades_legacy_id"),
        Index("ix_paper_trades_user_timestamp", "user_id", "timestamp"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
    side: Mapped[str | None] = mapped_column(String(8))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserAccount(JsonbLegacyMixin, Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_user_accounts_legacy_id"),
        UniqueConstraint("username", name="uq_user_accounts_username"),
        UniqueConstraint("email", name="uq_user_accounts_email"),
        Index("ix_user_accounts_active", "is_active"),
    )

    username: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserSessionDocument(JsonbLegacyMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_user_sessions_legacy_id"),
        UniqueConstraint("session_id", name="uq_user_sessions_session_id"),
        Index("ix_user_sessions_user_expires", "user_id", "expires_at"),
        Index("ix_user_sessions_expires", "expires_at"),
    )

    session_id: Mapped[str] = mapped_column(String(160), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LoginAttemptDocument(JsonbLegacyMixin, Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_login_attempts_legacy_id"),
        Index("ix_login_attempts_username_timestamp", "username", "timestamp"),
        Index("ix_login_attempts_ip_timestamp", "ip_address", "timestamp"),
        Index("ix_login_attempts_success_timestamp", "success", "timestamp"),
    )

    user_id: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool | None] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(160))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OperationLogDocument(JsonbLegacyMixin, Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_operations_legacy_id"),
        Index("ix_operations_user_timestamp", "user_id", "timestamp"),
        Index("ix_operations_action_success", "action_type", "success"),
    )

    user_id: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool | None] = mapped_column(Boolean)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DatabaseBackupDocument(JsonbLegacyMixin, Base):
    __tablename__ = "database_backups"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_database_backups_legacy_id"),
        Index("ix_database_backups_created_by", "created_by"),
    )

    name: Mapped[str | None] = mapped_column(String(160))
    filename: Mapped[str | None] = mapped_column(String(256))
    created_by: Mapped[str | None] = mapped_column(String(128))
    backup_type: Mapped[str | None] = mapped_column(String(32))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class NotificationDocument(JsonbLegacyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_notifications_legacy_id"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_status", "user_id", "status"),
        Index("ix_notifications_user_type", "user_id", "type"),
    )

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(16))
    severity: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TokenUsageDocument(JsonbLegacyMixin, Base):
    __tablename__ = "token_usage"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_token_usage_legacy_id"),
        Index("ix_token_usage_provider_model_timestamp", "provider", "model_name", "timestamp"),
        Index("ix_token_usage_session", "session_id"),
    )

    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    session_id: Mapped[str | None] = mapped_column(String(128))
    analysis_type: Mapped[str | None] = mapped_column(String(64))
    stock_code: Mapped[str | None] = mapped_column(String(32))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    currency: Mapped[str | None] = mapped_column(String(8))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InternalMessageDocument(JsonbLegacyMixin, Base):
    __tablename__ = "internal_messages"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_internal_messages_legacy_id"),
        UniqueConstraint("message_id", name="uq_internal_messages_message_id"),
        Index("ix_internal_messages_symbol_created", "symbol", "created_time"),
        Index("ix_internal_messages_type_category", "message_type", "category"),
        Index("ix_internal_messages_access_importance", "access_level", "importance"),
    )

    message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    message_type: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str | None] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(128))
    importance: Mapped[str | None] = mapped_column(String(32))
    access_level: Mapped[str | None] = mapped_column(String(32))
    rating: Mapped[str | None] = mapped_column(String(32))
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SocialMediaMessageDocument(JsonbLegacyMixin, Base):
    __tablename__ = "social_media_messages"
    __table_args__ = (
        UniqueConstraint("legacy_id", name="uq_social_media_messages_legacy_id"),
        UniqueConstraint("message_id", "platform", name="uq_social_media_messages_message_platform"),
        Index("ix_social_media_symbol_publish", "symbol", "publish_time"),
        Index("ix_social_media_platform_type", "platform", "message_type"),
        Index("ix_social_media_sentiment_importance", "sentiment", "importance"),
    )

    message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32))
    message_type: Mapped[str | None] = mapped_column(String(64))
    sentiment: Mapped[str | None] = mapped_column(String(32))
    importance: Mapped[str | None] = mapped_column(String(32))
    publish_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    influence_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    engagement_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    verified: Mapped[bool | None] = mapped_column(Boolean)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
