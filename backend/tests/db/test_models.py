from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.db.models import (
    AnalysisBatchDocument,
    AnalysisReport,
    AnalysisResultDocument,
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
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SyncStatusDocument,
    SocialMediaMessageDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)


def test_migrated_tables_keep_legacy_id_and_jsonb_payload():
    expected_tables = {
        "stock_basic_info",
        "market_quotes",
        "stock_daily_quotes",
        "stock_financial_data",
        "stock_news",
        "analysis_tasks",
        "analysis_reports",
        "analysis_batches",
        "analysis_results",
        "system_config_documents",
        "sync_status",
        "scheduler_executions",
        "scheduler_history",
        "scheduler_metadata",
        "user_favorites",
        "user_tags",
        "paper_accounts",
        "paper_positions",
        "paper_orders",
        "paper_trades",
        "user_accounts",
        "user_sessions",
        "login_attempts",
        "operation_logs",
        "database_backups",
        "notifications",
        "token_usage",
        "internal_messages",
        "social_media_messages",
    }

    assert expected_tables.issubset(Base.metadata.tables)

    for table_name in expected_tables:
        table = Base.metadata.tables[table_name]
        assert "legacy_id" in table.columns
        assert "payload" in table.columns
        assert isinstance(table.columns["payload"].type, JSONB)
        assert _has_unique_constraint(table, "legacy_id")


def test_stock_screening_hot_fields_are_split_columns():
    assert _has_columns(
        StockBasicInfo.__table__,
        {
            "code",
            "source",
            "name",
            "industry",
            "area",
            "market",
            "total_mv",
            "circ_mv",
            "pe",
            "pb",
            "pe_ttm",
            "pb_mrq",
            "updated_at",
        },
    )
    assert _has_columns(
        MarketQuote.__table__,
        {
            "code",
            "source",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "pct_chg",
            "amount",
            "volume",
            "updated_at",
        },
    )
    assert _has_columns(
        StockDailyQuote.__table__,
        {
            "symbol",
            "code",
            "full_symbol",
            "market",
            "trade_date",
            "period",
            "data_source",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "volume",
            "amount",
            "change",
            "pct_chg",
            "deleted",
            "updated_at",
        },
    )
    assert _has_columns(
        StockFinancialData.__table__,
        {
            "code",
            "data_source",
            "report_period",
            "roe",
            "roa",
            "netprofit_margin",
            "gross_margin",
            "updated_at",
        },
    )
    assert _has_columns(
        StockNewsDocument.__table__,
        {
            "symbol",
            "market",
            "title",
            "url",
            "data_source",
            "category",
            "sentiment",
            "importance",
            "publish_time",
            "deleted",
            "updated_at",
        },
    )


def test_hot_fields_have_expected_indexes_and_uniqueness():
    indexes = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    constraints = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "uq_stock_basic_info_code_source" in constraints
    assert "uq_market_quotes_code_source" in constraints
    assert "uq_stock_daily_quotes_symbol_date_source_period" in constraints
    assert "uq_stock_financial_data_code_source_period" in constraints
    assert "uq_stock_news_legacy_id" in constraints
    assert "uq_analysis_tasks_task_id" in constraints
    assert "uq_analysis_reports_analysis_id" in constraints
    assert "uq_analysis_batches_batch_id" in constraints
    assert "uq_analysis_results_legacy_id" in constraints
    assert "uq_sync_status_job" in constraints
    assert "uq_scheduler_history_legacy_id" in constraints
    assert "uq_scheduler_metadata_job_id" in constraints
    assert "uq_user_favorites_user_stock" in constraints
    assert "uq_user_tags_user_name" in constraints
    assert "uq_paper_accounts_user_id" in constraints
    assert "uq_paper_positions_user_code" in constraints
    assert "uq_user_accounts_username" in constraints
    assert "uq_user_sessions_session_id" in constraints
    assert "uq_login_attempts_legacy_id" in constraints
    assert "uq_operation_logs_legacy_id" in constraints
    assert "uq_database_backups_legacy_id" in constraints
    assert "uq_notifications_legacy_id" in constraints
    assert "uq_token_usage_legacy_id" in constraints
    assert "uq_internal_messages_message_id" in constraints
    assert "uq_social_media_messages_message_platform" in constraints
    assert {
        "ix_stock_basic_info_industry",
        "ix_stock_basic_info_total_mv",
        "ix_stock_basic_info_pe",
        "ix_stock_basic_info_pb",
        "ix_market_quotes_pct_chg",
        "ix_market_quotes_amount",
        "ix_market_quotes_updated_at",
        "ix_stock_daily_quotes_symbol_date",
        "ix_stock_daily_quotes_trade_date",
        "ix_stock_daily_quotes_market_source",
        "ix_stock_financial_data_report_period",
        "ix_stock_news_symbol_publish_time",
        "ix_stock_news_source_category",
        "ix_stock_news_sentiment_importance",
        "ix_analysis_tasks_user_status_created",
        "ix_analysis_reports_task_id",
        "ix_analysis_batches_user_status_created",
        "ix_analysis_results_task_user_created",
        "ix_sync_status_status_finished",
        "ix_scheduler_executions_job_status_timestamp",
        "ix_scheduler_history_job_status_timestamp",
        "ix_user_favorites_user_id",
        "ix_user_tags_user_sort",
        "ix_paper_positions_user_id",
        "ix_paper_orders_user_created",
        "ix_paper_trades_user_timestamp",
        "ix_user_accounts_active",
        "ix_user_sessions_user_expires",
        "ix_user_sessions_expires",
        "ix_login_attempts_username_timestamp",
        "ix_login_attempts_ip_timestamp",
        "ix_login_attempts_success_timestamp",
        "ix_operation_logs_user_timestamp",
        "ix_operation_logs_action_success",
        "ix_database_backups_created_by",
        "ix_notifications_user_created",
        "ix_notifications_user_status",
        "ix_notifications_user_type",
        "ix_token_usage_provider_model_timestamp",
        "ix_token_usage_session",
        "ix_internal_messages_symbol_created",
        "ix_internal_messages_type_category",
        "ix_internal_messages_access_importance",
        "ix_social_media_symbol_publish",
        "ix_social_media_platform_type",
        "ix_social_media_sentiment_importance",
    }.issubset(indexes)


def test_status_tables_keep_query_fields_split_from_payload():
    assert _has_columns(
        SyncStatusDocument.__table__,
        {"job", "status", "started_at", "finished_at", "duration", "updated_at"},
    )
    assert _has_columns(
        SchedulerExecution.__table__,
        {"job_id", "status", "progress", "progress_message", "timestamp", "cancel_requested"},
    )
    assert _has_columns(
        SchedulerHistoryDocument.__table__,
        {"job_id", "action", "status", "timestamp", "deleted"},
    )
    assert _has_columns(
        SchedulerMetadataDocument.__table__,
        {"job_id", "display_name", "description", "deleted"},
    )


def test_analysis_extension_tables_keep_query_fields_split_from_payload():
    assert _has_columns(
        AnalysisReport.__table__,
        {"analysis_id", "task_id", "user_id", "stock_symbol", "analysis_date", "summary"},
    )
    assert _has_columns(
        AnalysisBatchDocument.__table__,
        {"batch_id", "user_id", "status", "total_tasks", "deleted"},
    )
    assert _has_columns(
        AnalysisResultDocument.__table__,
        {"task_id", "user_id", "stock_symbol", "status", "deleted"},
    )


def test_user_preference_tables_keep_query_fields_split_from_payload():
    assert _has_columns(
        UserFavorite.__table__,
        {"user_id", "stock_code", "stock_name", "market", "deleted", "updated_at"},
    )
    assert _has_columns(
        UserTag.__table__,
        {"user_id", "tag_id", "name", "color", "sort_order", "deleted", "updated_at"},
    )


def test_paper_trading_tables_keep_query_fields_split_from_payload():
    assert _has_columns(PaperAccount.__table__, {"user_id", "deleted", "updated_at"})
    assert _has_columns(
        PaperPosition.__table__,
        {"user_id", "code", "market", "currency", "quantity", "deleted"},
    )
    assert _has_columns(PaperOrder.__table__, {"user_id", "code", "side", "status", "deleted"})
    assert _has_columns(PaperTrade.__table__, {"user_id", "code", "side", "timestamp", "deleted"})


def test_user_account_table_keeps_auth_fields_split_from_payload():
    assert _has_columns(
        UserAccount.__table__,
        {"username", "email", "is_active", "is_admin", "deleted", "updated_at"},
    )


def test_security_session_tables_keep_ttl_and_audit_fields_split_from_payload():
    assert _has_columns(
        UserSessionDocument.__table__,
        {
            "session_id",
            "user_id",
            "username",
            "ip_address",
            "user_agent",
            "expires_at",
            "last_activity_at",
            "deleted",
        },
    )
    assert _has_columns(
        LoginAttemptDocument.__table__,
        {"user_id", "username", "ip_address", "success", "reason", "timestamp", "deleted"},
    )


def test_operational_tables_keep_query_fields_split_from_payload():
    assert _has_columns(
        OperationLogDocument.__table__,
        {"user_id", "username", "action_type", "success", "timestamp", "deleted"},
    )
    assert _has_columns(
        DatabaseBackupDocument.__table__,
        {"name", "filename", "created_by", "backup_type", "deleted"},
    )


def test_dynamic_business_tables_keep_query_fields_split_from_payload():
    assert _has_columns(
        NotificationDocument.__table__,
        {"user_id", "type", "status", "severity", "title", "deleted"},
    )
    assert _has_columns(
        TokenUsageDocument.__table__,
        {"provider", "model_name", "session_id", "timestamp", "input_tokens", "output_tokens", "cost", "currency", "deleted"},
    )
    assert _has_columns(
        InternalMessageDocument.__table__,
        {"message_id", "symbol", "message_type", "category", "access_level", "importance", "created_time", "deleted"},
    )
    assert _has_columns(
        SocialMediaMessageDocument.__table__,
        {"message_id", "platform", "symbol", "message_type", "sentiment", "importance", "publish_time", "deleted"},
    )


def _has_columns(table, columns: set[str]) -> bool:
    return columns.issubset(set(table.columns.keys()))


def _has_unique_constraint(table, column_name: str) -> bool:
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {column_name}
        for constraint in table.constraints
    )
