"""initial postgres jsonb schema

Revision ID: 0001_initial_postgres_jsonb
Revises:
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_postgres_jsonb"
down_revision = None
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "postgres_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=256), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection",
            "document_id",
            name="uq_postgres_documents_collection_document_id",
        ),
    )
    op.create_index(
        "ix_postgres_documents_collection", "postgres_documents", ["collection"]
    )
    op.create_index(
        "ix_postgres_documents_updated_at", "postgres_documents", ["updated_at"]
    )

    op.create_table(
        "stock_basic_info",
        *_base_columns(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("area", sa.String(length=128), nullable=True),
        sa.Column("market", sa.String(length=32), nullable=True),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("total_mv", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("circ_mv", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("pe", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pb", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pe_ttm", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pb_mrq", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_stock_basic_info_legacy_id"),
        sa.UniqueConstraint("code", "source", name="uq_stock_basic_info_code_source"),
    )
    op.create_index("ix_stock_basic_info_industry", "stock_basic_info", ["industry"])
    op.create_index("ix_stock_basic_info_total_mv", "stock_basic_info", ["total_mv"])
    op.create_index("ix_stock_basic_info_pe", "stock_basic_info", ["pe"])
    op.create_index("ix_stock_basic_info_pb", "stock_basic_info", ["pb"])

    op.create_table(
        "market_quotes",
        *_base_columns(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("open", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pre_close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pct_chg", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("amount", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("volume", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_market_quotes_legacy_id"),
        sa.UniqueConstraint("code", "source", name="uq_market_quotes_code_source"),
    )
    op.create_index("ix_market_quotes_pct_chg", "market_quotes", ["pct_chg"])
    op.create_index("ix_market_quotes_amount", "market_quotes", ["amount"])
    op.create_index("ix_market_quotes_updated_at", "market_quotes", ["updated_at"])

    op.create_table(
        "stock_daily_quotes",
        *_base_columns(),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("full_symbol", sa.String(length=32), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("data_source", sa.String(length=32), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pre_close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("volume", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("amount", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("change", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("pct_chg", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_stock_daily_quotes_legacy_id"),
        sa.UniqueConstraint(
            "symbol",
            "trade_date",
            "data_source",
            "period",
            name="uq_stock_daily_quotes_symbol_date_source_period",
        ),
    )
    op.create_index(
        "ix_stock_daily_quotes_market_source",
        "stock_daily_quotes",
        ["market", "data_source"],
    )
    op.create_index(
        "ix_stock_daily_quotes_symbol_date",
        "stock_daily_quotes",
        ["symbol", "trade_date"],
    )
    op.create_index(
        "ix_stock_daily_quotes_trade_date", "stock_daily_quotes", ["trade_date"]
    )

    op.create_table(
        "stock_financial_data",
        *_base_columns(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("data_source", sa.String(length=32), nullable=False),
        sa.Column("report_period", sa.String(length=32), nullable=False),
        sa.Column("roe", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("roa", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("netprofit_margin", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("gross_margin", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_stock_financial_data_legacy_id"),
        sa.UniqueConstraint(
            "code",
            "data_source",
            "report_period",
            name="uq_stock_financial_data_code_source_period",
        ),
    )
    op.create_index(
        "ix_stock_financial_data_report_period",
        "stock_financial_data",
        ["report_period"],
    )

    op.create_table(
        "stock_news",
        *_base_columns(),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("sentiment", sa.String(length=32), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=True),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_stock_news_legacy_id"),
    )
    op.create_index(
        "ix_stock_news_sentiment_importance", "stock_news", ["sentiment", "importance"]
    )
    op.create_index(
        "ix_stock_news_source_category", "stock_news", ["data_source", "category"]
    )
    op.create_index(
        "ix_stock_news_symbol_publish_time", "stock_news", ["symbol", "publish_time"]
    )

    op.create_table(
        "analysis_tasks",
        *_base_columns(),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("stock_symbol", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_analysis_tasks_legacy_id"),
        sa.UniqueConstraint("task_id", name="uq_analysis_tasks_task_id"),
    )
    op.create_index("ix_analysis_tasks_task_id", "analysis_tasks", ["task_id"])
    op.create_index(
        "ix_analysis_tasks_user_status_created",
        "analysis_tasks",
        ["user_id", "status", "created_at"],
    )

    op.create_table(
        "analysis_reports",
        *_base_columns(),
        sa.Column("analysis_id", sa.String(length=160), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("stock_symbol", sa.String(length=32), nullable=True),
        sa.Column("analysis_date", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.UniqueConstraint("analysis_id", name="uq_analysis_reports_analysis_id"),
        sa.UniqueConstraint("legacy_id", name="uq_analysis_reports_legacy_id"),
    )
    op.create_index(
        "ix_analysis_reports_analysis_id", "analysis_reports", ["analysis_id"]
    )
    op.create_index("ix_analysis_reports_task_id", "analysis_reports", ["task_id"])
    op.create_index(
        "ix_analysis_reports_user_symbol_date",
        "analysis_reports",
        ["user_id", "stock_symbol", "analysis_date"],
    )

    op.create_table(
        "analysis_batches",
        *_base_columns(),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("total_tasks", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("batch_id", name="uq_analysis_batches_batch_id"),
        sa.UniqueConstraint("legacy_id", name="uq_analysis_batches_legacy_id"),
    )
    op.create_index(
        "ix_analysis_batches_user_status_created",
        "analysis_batches",
        ["user_id", "status", "created_at"],
    )

    op.create_table(
        "analysis_results",
        *_base_columns(),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("stock_symbol", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_analysis_results_legacy_id"),
    )
    op.create_index(
        "ix_analysis_results_task_user_created",
        "analysis_results",
        ["task_id", "user_id", "created_at"],
    )

    op.create_table(
        "system_config_documents",
        *_base_columns(),
        sa.Column("config_key", sa.String(length=160), nullable=False),
        sa.Column("config_type", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_system_config_documents_legacy_id"),
        sa.UniqueConstraint("config_key", name="uq_system_config_documents_config_key"),
    )
    op.create_index(
        "ix_system_config_documents_config_type",
        "system_config_documents",
        ["config_type"],
    )

    op.create_table(
        "sync_status",
        *_base_columns(),
        sa.Column("job", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.UniqueConstraint("job", name="uq_sync_status_job"),
        sa.UniqueConstraint("legacy_id", name="uq_sync_status_legacy_id"),
    )
    op.create_index(
        "ix_sync_status_status_finished", "sync_status", ["status", "finished_at"]
    )

    op.create_table(
        "scheduler_executions",
        *_base_columns(),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("progress_message", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("legacy_id", name="uq_scheduler_executions_legacy_id"),
    )
    op.create_index(
        "ix_scheduler_executions_job_status_timestamp",
        "scheduler_executions",
        ["job_id", "status", "timestamp"],
    )

    op.create_table(
        "scheduler_history",
        *_base_columns(),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_scheduler_history_legacy_id"),
    )
    op.create_index(
        "ix_scheduler_history_job_status_timestamp",
        "scheduler_history",
        ["job_id", "status", "timestamp"],
    )

    op.create_table(
        "scheduler_metadata",
        *_base_columns(),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_scheduler_metadata_job_id"),
        sa.UniqueConstraint("legacy_id", name="uq_scheduler_metadata_legacy_id"),
    )

    op.create_table(
        "user_favorites",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("stock_code", sa.String(length=32), nullable=False),
        sa.Column("stock_name", sa.String(length=128), nullable=True),
        sa.Column("market", sa.String(length=32), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_user_favorites_legacy_id"),
        sa.UniqueConstraint(
            "user_id", "stock_code", name="uq_user_favorites_user_stock"
        ),
    )
    op.create_index("ix_user_favorites_user_id", "user_favorites", ["user_id"])

    op.create_table(
        "user_tags",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("tag_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_user_tags_legacy_id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tags_user_name"),
    )
    op.create_index("ix_user_tags_user_sort", "user_tags", ["user_id", "sort_order"])

    op.create_table(
        "paper_accounts",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_paper_accounts_legacy_id"),
        sa.UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
    )

    op.create_table(
        "paper_positions",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_paper_positions_legacy_id"),
        sa.UniqueConstraint("user_id", "code", name="uq_paper_positions_user_code"),
    )
    op.create_index("ix_paper_positions_user_id", "paper_positions", ["user_id"])

    op.create_table(
        "paper_orders",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_paper_orders_legacy_id"),
    )
    op.create_index(
        "ix_paper_orders_user_created", "paper_orders", ["user_id", "created_at"]
    )

    op.create_table(
        "paper_trades",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_paper_trades_legacy_id"),
    )
    op.create_index(
        "ix_paper_trades_user_timestamp", "paper_trades", ["user_id", "timestamp"]
    )

    op.create_table(
        "user_accounts",
        *_base_columns(),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("email", name="uq_user_accounts_email"),
        sa.UniqueConstraint("legacy_id", name="uq_user_accounts_legacy_id"),
        sa.UniqueConstraint("username", name="uq_user_accounts_username"),
    )
    op.create_index("ix_user_accounts_active", "user_accounts", ["is_active"])

    op.create_table(
        "user_sessions",
        *_base_columns(),
        sa.Column("session_id", sa.String(length=160), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_user_sessions_legacy_id"),
        sa.UniqueConstraint("session_id", name="uq_user_sessions_session_id"),
    )
    op.create_index("ix_user_sessions_expires", "user_sessions", ["expires_at"])
    op.create_index(
        "ix_user_sessions_user_expires", "user_sessions", ["user_id", "expires_at"]
    )

    op.create_table(
        "login_attempts",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_login_attempts_legacy_id"),
    )
    op.create_index(
        "ix_login_attempts_ip_timestamp", "login_attempts", ["ip_address", "timestamp"]
    )
    op.create_index(
        "ix_login_attempts_success_timestamp",
        "login_attempts",
        ["success", "timestamp"],
    )
    op.create_index(
        "ix_login_attempts_username_timestamp",
        "login_attempts",
        ["username", "timestamp"],
    )

    op.create_table(
        "operation_logs",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_operation_logs_legacy_id"),
    )
    op.create_index(
        "ix_operation_logs_action_success", "operation_logs", ["action_type", "success"]
    )
    op.create_index(
        "ix_operation_logs_user_timestamp", "operation_logs", ["user_id", "timestamp"]
    )

    op.create_table(
        "database_backups",
        *_base_columns(),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("backup_type", sa.String(length=32), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_database_backups_legacy_id"),
    )
    op.create_index(
        "ix_database_backups_created_by", "database_backups", ["created_by"]
    )

    op.create_table(
        "notifications",
        *_base_columns(),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_notifications_legacy_id"),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_notifications_user_status", "notifications", ["user_id", "status"]
    )
    op.create_index("ix_notifications_user_type", "notifications", ["user_id", "type"])

    op.create_table(
        "token_usage",
        *_base_columns(),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("analysis_type", sa.String(length=64), nullable=True),
        sa.Column("stock_code", sa.String(length=32), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_token_usage_legacy_id"),
    )
    op.create_index(
        "ix_token_usage_provider_model_timestamp",
        "token_usage",
        ["provider", "model_name", "timestamp"],
    )
    op.create_index("ix_token_usage_session", "token_usage", ["session_id"])

    op.create_table(
        "internal_messages",
        *_base_columns(),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("message_type", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=True),
        sa.Column("access_level", sa.String(length=32), nullable=True),
        sa.Column("rating", sa.String(length=32), nullable=True),
        sa.Column("confidence_level", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_internal_messages_legacy_id"),
        sa.UniqueConstraint("message_id", name="uq_internal_messages_message_id"),
    )
    op.create_index(
        "ix_internal_messages_access_importance",
        "internal_messages",
        ["access_level", "importance"],
    )
    op.create_index(
        "ix_internal_messages_symbol_created",
        "internal_messages",
        ["symbol", "created_time"],
    )
    op.create_index(
        "ix_internal_messages_type_category",
        "internal_messages",
        ["message_type", "category"],
    )

    op.create_table(
        "social_media_messages",
        *_base_columns(),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("message_type", sa.String(length=64), nullable=True),
        sa.Column("sentiment", sa.String(length=32), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=True),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("influence_score", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_social_media_messages_legacy_id"),
        sa.UniqueConstraint(
            "message_id", "platform", name="uq_social_media_messages_message_platform"
        ),
    )
    op.create_index(
        "ix_social_media_platform_type",
        "social_media_messages",
        ["platform", "message_type"],
    )
    op.create_index(
        "ix_social_media_sentiment_importance",
        "social_media_messages",
        ["sentiment", "importance"],
    )
    op.create_index(
        "ix_social_media_symbol_publish",
        "social_media_messages",
        ["symbol", "publish_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_postgres_documents_updated_at", table_name="postgres_documents")
    op.drop_index("ix_postgres_documents_collection", table_name="postgres_documents")
    op.drop_table("postgres_documents")
    op.drop_index("ix_social_media_symbol_publish", table_name="social_media_messages")
    op.drop_index(
        "ix_social_media_sentiment_importance", table_name="social_media_messages"
    )
    op.drop_index("ix_social_media_platform_type", table_name="social_media_messages")
    op.drop_table("social_media_messages")
    op.drop_index("ix_internal_messages_type_category", table_name="internal_messages")
    op.drop_index("ix_internal_messages_symbol_created", table_name="internal_messages")
    op.drop_index(
        "ix_internal_messages_access_importance", table_name="internal_messages"
    )
    op.drop_table("internal_messages")
    op.drop_index("ix_token_usage_session", table_name="token_usage")
    op.drop_index("ix_token_usage_provider_model_timestamp", table_name="token_usage")
    op.drop_table("token_usage")
    op.drop_index("ix_notifications_user_type", table_name="notifications")
    op.drop_index("ix_notifications_user_status", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_database_backups_created_by", table_name="database_backups")
    op.drop_table("database_backups")
    op.drop_index("ix_operation_logs_user_timestamp", table_name="operation_logs")
    op.drop_index("ix_operation_logs_action_success", table_name="operation_logs")
    op.drop_table("operation_logs")
    op.drop_index("ix_login_attempts_username_timestamp", table_name="login_attempts")
    op.drop_index("ix_login_attempts_success_timestamp", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip_timestamp", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_user_sessions_user_expires", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_user_accounts_active", table_name="user_accounts")
    op.drop_table("user_accounts")
    op.drop_index("ix_paper_trades_user_timestamp", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("ix_paper_orders_user_created", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_paper_positions_user_id", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_table("paper_accounts")
    op.drop_index("ix_user_tags_user_sort", table_name="user_tags")
    op.drop_table("user_tags")
    op.drop_index("ix_user_favorites_user_id", table_name="user_favorites")
    op.drop_table("user_favorites")
    op.drop_table("scheduler_metadata")
    op.drop_index(
        "ix_scheduler_history_job_status_timestamp", table_name="scheduler_history"
    )
    op.drop_table("scheduler_history")
    op.drop_index(
        "ix_scheduler_executions_job_status_timestamp",
        table_name="scheduler_executions",
    )
    op.drop_table("scheduler_executions")
    op.drop_index("ix_sync_status_status_finished", table_name="sync_status")
    op.drop_table("sync_status")
    op.drop_index(
        "ix_system_config_documents_config_type", table_name="system_config_documents"
    )
    op.drop_table("system_config_documents")
    op.drop_index("ix_analysis_reports_user_symbol_date", table_name="analysis_reports")
    op.drop_index("ix_analysis_reports_task_id", table_name="analysis_reports")
    op.drop_index("ix_analysis_reports_analysis_id", table_name="analysis_reports")
    op.drop_index(
        "ix_analysis_results_task_user_created", table_name="analysis_results"
    )
    op.drop_table("analysis_results")
    op.drop_index(
        "ix_analysis_batches_user_status_created", table_name="analysis_batches"
    )
    op.drop_table("analysis_batches")
    op.drop_table("analysis_reports")
    op.drop_index("ix_analysis_tasks_user_status_created", table_name="analysis_tasks")
    op.drop_index("ix_analysis_tasks_task_id", table_name="analysis_tasks")
    op.drop_table("analysis_tasks")
    op.drop_index("ix_stock_news_symbol_publish_time", table_name="stock_news")
    op.drop_index("ix_stock_news_source_category", table_name="stock_news")
    op.drop_index("ix_stock_news_sentiment_importance", table_name="stock_news")
    op.drop_table("stock_news")
    op.drop_index(
        "ix_stock_financial_data_report_period", table_name="stock_financial_data"
    )
    op.drop_table("stock_financial_data")
    op.drop_index("ix_stock_daily_quotes_trade_date", table_name="stock_daily_quotes")
    op.drop_index("ix_stock_daily_quotes_symbol_date", table_name="stock_daily_quotes")
    op.drop_index(
        "ix_stock_daily_quotes_market_source", table_name="stock_daily_quotes"
    )
    op.drop_table("stock_daily_quotes")
    op.drop_index("ix_market_quotes_updated_at", table_name="market_quotes")
    op.drop_index("ix_market_quotes_amount", table_name="market_quotes")
    op.drop_index("ix_market_quotes_pct_chg", table_name="market_quotes")
    op.drop_table("market_quotes")
    op.drop_index("ix_stock_basic_info_pb", table_name="stock_basic_info")
    op.drop_index("ix_stock_basic_info_pe", table_name="stock_basic_info")
    op.drop_index("ix_stock_basic_info_total_mv", table_name="stock_basic_info")
    op.drop_index("ix_stock_basic_info_industry", table_name="stock_basic_info")
    op.drop_table("stock_basic_info")
