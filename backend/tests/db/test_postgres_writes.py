from sqlalchemy.dialects import postgresql

from app.db.models import (
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
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SystemConfigDocument,
    SyncStatusDocument,
    SocialMediaMessageDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)
from app.db.postgres_writes import (
    build_analysis_report_upsert,
    build_analysis_batch_upsert,
    build_analysis_result_upsert,
    build_analysis_task_upsert,
    build_database_backup_upsert,
    build_internal_message_upsert,
    build_login_attempt_upsert,
    build_market_quote_upsert,
    build_notification_upsert,
    build_operation_log_upsert,
    build_paper_account_upsert,
    build_paper_order_upsert,
    build_paper_position_upsert,
    build_paper_trade_upsert,
    build_scheduler_execution_upsert,
    build_scheduler_history_upsert,
    build_scheduler_metadata_upsert,
    build_stock_basic_info_upsert,
    build_stock_daily_quote_upsert,
    build_stock_financial_data_upsert,
    build_stock_news_upsert,
    build_system_config_document_upsert,
    build_sync_status_upsert,
    build_social_media_message_upsert,
    build_token_usage_upsert,
    build_user_account_upsert,
    build_user_favorite_upsert,
    build_user_session_upsert,
    build_user_tag_upsert,
)


def test_stock_basic_info_upsert_conflicts_on_hot_business_key():
    statement = build_stock_basic_info_upsert({"code": "000001", "source": "tushare"})
    sql = _compile(statement)

    assert "INSERT INTO stock_basic_info" in sql
    assert "ON CONFLICT (code, source) DO UPDATE" in sql
    assert "payload = excluded.payload" in sql
    assert statement.table is StockBasicInfo.__table__


def test_market_quote_upsert_conflicts_on_hot_business_key():
    statement = build_market_quote_upsert({"code": "000001", "source": "akshare"})
    sql = _compile(statement)

    assert "INSERT INTO market_quotes" in sql
    assert "ON CONFLICT (code, source) DO UPDATE" in sql
    assert statement.table is MarketQuote.__table__


def test_stock_daily_quote_upsert_conflicts_on_history_business_key():
    statement = build_stock_daily_quote_upsert(
        {
            "symbol": "000001",
            "trade_date": "2026-06-03",
            "data_source": "tushare",
            "period": "daily",
        }
    )
    sql = _compile(statement)

    assert "INSERT INTO stock_daily_quotes" in sql
    assert "ON CONFLICT (symbol, trade_date, data_source, period) DO UPDATE" in sql
    assert statement.table is StockDailyQuote.__table__


def test_stock_financial_data_upsert_conflicts_on_period_key():
    statement = build_stock_financial_data_upsert(
        {"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}
    )
    sql = _compile(statement)

    assert "INSERT INTO stock_financial_data" in sql
    assert "ON CONFLICT (code, data_source, report_period) DO UPDATE" in sql
    assert statement.table is StockFinancialData.__table__


def test_stock_news_upsert_conflicts_on_legacy_id():
    statement = build_stock_news_upsert(
        {
            "symbol": "000001",
            "title": "平安银行新闻",
            "url": "https://example.com/news/1",
            "publish_time": "2026-06-03T10:00:00",
            "data_source": "akshare",
        }
    )
    sql = _compile(statement)

    assert "INSERT INTO stock_news" in sql
    assert "ON CONFLICT (legacy_id) DO UPDATE" in sql
    assert statement.table is StockNewsDocument.__table__


def test_analysis_task_upsert_conflicts_on_task_id():
    statement = build_analysis_task_upsert({"task_id": "task-1", "status": "running"})
    sql = _compile(statement)

    assert "INSERT INTO analysis_tasks" in sql
    assert "ON CONFLICT (task_id) DO UPDATE" in sql
    assert statement.table is AnalysisTask.__table__


def test_analysis_report_upsert_conflicts_on_analysis_id():
    statement = build_analysis_report_upsert({"analysis_id": "analysis-1", "summary": "buy"})
    sql = _compile(statement)

    assert "INSERT INTO analysis_reports" in sql
    assert "ON CONFLICT (analysis_id) DO UPDATE" in sql
    assert statement.table is AnalysisReport.__table__


def test_analysis_batch_and_result_upserts_use_expected_conflicts():
    batch = build_analysis_batch_upsert({"batch_id": "batch-1", "user_id": "user-1"})
    result = build_analysis_result_upsert({"legacy_id": "result-1", "task_id": "task-1"})

    assert "INSERT INTO analysis_batches" in _compile(batch)
    assert "ON CONFLICT (batch_id) DO UPDATE" in _compile(batch)
    assert batch.table is AnalysisBatchDocument.__table__
    assert "INSERT INTO analysis_results" in _compile(result)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(result)
    assert result.table is AnalysisResultDocument.__table__


def test_sync_status_upsert_conflicts_on_job():
    statement = build_sync_status_upsert({"job": "example_sdk_sync", "status": "completed"})
    sql = _compile(statement)

    assert "INSERT INTO sync_status" in sql
    assert "ON CONFLICT (job) DO UPDATE" in sql
    assert statement.table is SyncStatusDocument.__table__


def test_scheduler_execution_upsert_conflicts_on_legacy_id():
    statement = build_scheduler_execution_upsert(
        {"legacy_id": "scheduler-1", "job_id": "tushare_daily", "progress": 50}
    )
    sql = _compile(statement)

    assert "INSERT INTO scheduler_executions" in sql
    assert "ON CONFLICT (legacy_id) DO UPDATE" in sql
    assert statement.table is SchedulerExecution.__table__


def test_scheduler_history_and_metadata_upserts_use_expected_conflicts():
    history = build_scheduler_history_upsert(
        {"job_id": "daily_sync", "action": "trigger", "timestamp": "2026-06-03T11:00:00"}
    )
    metadata = build_scheduler_metadata_upsert(
        {"job_id": "daily_sync", "display_name": "每日同步"}
    )

    assert "INSERT INTO scheduler_history" in _compile(history)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(history)
    assert history.table is SchedulerHistoryDocument.__table__
    assert "INSERT INTO scheduler_metadata" in _compile(metadata)
    assert "ON CONFLICT (job_id) DO UPDATE" in _compile(metadata)
    assert metadata.table is SchedulerMetadataDocument.__table__


def test_system_config_document_upsert_conflicts_on_namespaced_config_key():
    statement = build_system_config_document_upsert(
        {"provider": "dashscope", "enabled": True},
        collection="llm_providers",
    )
    sql = _compile(statement)

    assert "INSERT INTO system_config_documents" in sql
    assert "ON CONFLICT (config_key) DO UPDATE" in sql
    assert statement.table is SystemConfigDocument.__table__


def test_user_favorite_upsert_conflicts_on_user_stock():
    statement = build_user_favorite_upsert(
        {"user_id": "user-1", "stock_code": "000001", "stock_name": "平安银行"}
    )
    sql = _compile(statement)

    assert "INSERT INTO user_favorites" in sql
    assert "ON CONFLICT (user_id, stock_code) DO UPDATE" in sql
    assert statement.table is UserFavorite.__table__


def test_user_tag_upsert_conflicts_on_legacy_id():
    statement = build_user_tag_upsert(
        {"legacy_id": "tag-1", "user_id": "user-1", "name": "关注"}
    )
    sql = _compile(statement)

    assert "INSERT INTO user_tags" in sql
    assert "ON CONFLICT (legacy_id) DO UPDATE" in sql
    assert statement.table is UserTag.__table__


def test_paper_account_upsert_conflicts_on_user_id():
    statement = build_paper_account_upsert({"user_id": "user-1"})
    sql = _compile(statement)

    assert "INSERT INTO paper_accounts" in sql
    assert "ON CONFLICT (user_id) DO UPDATE" in sql
    assert statement.table is PaperAccount.__table__


def test_paper_position_upsert_conflicts_on_user_code():
    statement = build_paper_position_upsert({"user_id": "user-1", "code": "AAPL"})
    sql = _compile(statement)

    assert "INSERT INTO paper_positions" in sql
    assert "ON CONFLICT (user_id, code) DO UPDATE" in sql
    assert statement.table is PaperPosition.__table__


def test_paper_order_and_trade_upsert_conflict_on_legacy_id():
    order = build_paper_order_upsert({"legacy_id": "order-1", "user_id": "user-1"})
    trade = build_paper_trade_upsert({"legacy_id": "trade-1", "user_id": "user-1"})

    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(order)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(trade)
    assert order.table is PaperOrder.__table__
    assert trade.table is PaperTrade.__table__


def test_user_account_upsert_conflicts_on_username():
    statement = build_user_account_upsert(
        {"username": "admin", "email": "admin@example.com"}
    )
    sql = _compile(statement)

    assert "INSERT INTO user_accounts" in sql
    assert "ON CONFLICT (username) DO UPDATE" in sql
    assert statement.table is UserAccount.__table__


def test_security_session_upserts_use_expected_conflicts():
    session = build_user_session_upsert(
        {"session_id": "sess-1", "user_id": "user-1", "expires_at": "2026-06-04T00:00:00"}
    )
    attempt = build_login_attempt_upsert(
        {"legacy_id": "attempt-1", "username": "admin", "success": False}
    )

    assert "INSERT INTO user_sessions" in _compile(session)
    assert "ON CONFLICT (session_id) DO UPDATE" in _compile(session)
    assert session.table is UserSessionDocument.__table__
    assert "INSERT INTO login_attempts" in _compile(attempt)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(attempt)
    assert attempt.table is LoginAttemptDocument.__table__


def test_operational_upserts_conflict_on_legacy_id():
    log = build_operation_log_upsert({"legacy_id": "log-1", "user_id": "user-1"})
    backup = build_database_backup_upsert({"legacy_id": "backup-1", "name": "daily"})

    assert "INSERT INTO operation_logs" in _compile(log)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(log)
    assert log.table is OperationLogDocument.__table__
    assert "INSERT INTO database_backups" in _compile(backup)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(backup)
    assert backup.table is DatabaseBackupDocument.__table__


def test_dynamic_business_upserts_use_expected_conflicts():
    notification = build_notification_upsert({"legacy_id": "notif-1", "user_id": "user-1"})
    usage = build_token_usage_upsert(
        {
            "provider": "dashscope",
            "model_name": "qwen-plus",
            "session_id": "session-1",
            "timestamp": "2026-06-03T10:00:00",
        }
    )
    internal = build_internal_message_upsert({"message_id": "msg-1", "symbol": "000001"})
    social = build_social_media_message_upsert({"message_id": "social-1", "platform": "weibo"})

    assert "INSERT INTO notifications" in _compile(notification)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(notification)
    assert notification.table is NotificationDocument.__table__
    assert "INSERT INTO token_usage" in _compile(usage)
    assert "ON CONFLICT (legacy_id) DO UPDATE" in _compile(usage)
    assert usage.table is TokenUsageDocument.__table__
    assert "INSERT INTO internal_messages" in _compile(internal)
    assert "ON CONFLICT (message_id) DO UPDATE" in _compile(internal)
    assert internal.table is InternalMessageDocument.__table__
    assert "INSERT INTO social_media_messages" in _compile(social)
    assert "ON CONFLICT (message_id, platform) DO UPDATE" in _compile(social)
    assert social.table is SocialMediaMessageDocument.__table__


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
