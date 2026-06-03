from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_config_points_to_backend_migrations():
    alembic_ini = BACKEND_ROOT / "alembic.ini"

    assert alembic_ini.exists()

    text = alembic_ini.read_text(encoding="utf-8")
    assert "script_location = alembic" in text
    assert "sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/tradingagentscn" in text


def test_alembic_env_uses_settings_postgres_url_and_model_metadata():
    env_py = BACKEND_ROOT / "alembic" / "env.py"

    assert env_py.exists()

    text = env_py.read_text(encoding="utf-8")
    assert "from app.core.config import settings" in text
    assert "from app.db.base import Base" in text
    assert "import app.db.models" in text
    assert "target_metadata = Base.metadata" in text
    assert "settings.POSTGRES_URL" in text


def test_initial_migration_covers_jsonb_first_tables_and_legacy_id():
    versions = BACKEND_ROOT / "alembic" / "versions"
    migration_files = sorted(versions.glob("*initial_postgres_jsonb*.py"))

    assert len(migration_files) == 1

    text = migration_files[0].read_text(encoding="utf-8")
    for table_name in [
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
    ]:
        assert f'op.create_table("{table_name}"' in text

    assert text.count('"legacy_id"') >= 29
    assert 'sa.Column("payload", postgresql.JSONB' in text
    assert text.count("*_base_columns()") >= 29
    assert "uq_stock_basic_info_code_source" in text
    assert "uq_market_quotes_code_source" in text
    assert "uq_stock_daily_quotes_symbol_date_source_period" in text
    assert "uq_stock_financial_data_code_source_period" in text
    assert "uq_stock_news_legacy_id" in text
    assert "uq_analysis_tasks_task_id" in text
    assert "uq_analysis_reports_analysis_id" in text
    assert "ix_analysis_reports_task_id" in text
    assert "uq_analysis_batches_batch_id" in text
    assert "uq_analysis_results_legacy_id" in text
    assert "uq_sync_status_job" in text
    assert "uq_scheduler_executions_legacy_id" in text
    assert "uq_scheduler_history_legacy_id" in text
    assert "uq_scheduler_metadata_job_id" in text
    assert "uq_user_favorites_user_stock" in text
    assert "uq_user_tags_user_name" in text
    assert "uq_paper_accounts_user_id" in text
    assert "uq_paper_positions_user_code" in text
    assert "uq_paper_orders_legacy_id" in text
    assert "uq_paper_trades_legacy_id" in text
    assert "uq_user_accounts_username" in text
    assert "uq_user_sessions_session_id" in text
    assert "uq_login_attempts_legacy_id" in text
    assert "uq_operation_logs_legacy_id" in text
    assert "uq_database_backups_legacy_id" in text
    assert "uq_notifications_legacy_id" in text
    assert "uq_token_usage_legacy_id" in text
    assert "uq_internal_messages_message_id" in text
    assert "uq_social_media_messages_message_platform" in text
