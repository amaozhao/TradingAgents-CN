from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.db.document import (
    iter_user_favorite_documents,
    legacy_id_from_document,
    map_analysis_batch,
    map_analysis_report,
    map_analysis_result,
    map_analysis_task,
    map_database_backup,
    map_internal_message,
    map_login_attempt,
    map_market_quote,
    map_notification,
    map_operation_log,
    map_paper_account,
    map_paper_order,
    map_paper_position,
    map_paper_trade,
    map_scheduler_execution,
    map_scheduler_history,
    map_scheduler_metadata,
    map_social_media_message,
    map_stock_basic_info,
    map_stock_daily_quote,
    map_stock_financial_data,
    map_stock_news,
    map_sync_status,
    map_system_config_document,
    map_token_usage,
    map_user_account,
    map_user_favorite,
    map_user_session,
    map_user_tag,
    normalize_payload,
)
from app.db.store import _build_specialized_select
from app.db.ids import DocumentId
from app.models.table import SystemConfigDocument


def test_legacy_id_uses_postgres_document_id_and_payload_keeps_string_id():
    document_id = DocumentId()
    document = {
        "_id": document_id,
        "code": "000001",
        "updated_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
    }

    assert legacy_id_from_document(document) == str(document_id)
    assert normalize_payload(document) == {
        "_id": str(document_id),
        "code": "000001",
        "updated_at": "2026-06-03T00:00:00+00:00",
    }


def test_legacy_id_falls_back_to_existing_legacy_id():
    document = {"legacy_id": "manual-1", "code": "000001"}

    assert legacy_id_from_document(document) == "manual-1"


def test_stock_basic_info_mapper_splits_hot_fields_and_payload():
    document_id = DocumentId()
    values = map_stock_basic_info(
        {
            "_id": document_id,
            "code": "000001",
            "source": "tushare",
            "name": "平安银行",
            "industry": "银行",
            "area": "深圳",
            "market": "A",
            "list_date": "1991-04-03",
            "total_mv": "123.45",
            "circ_mv": 100,
            "pe": "8.1",
            "pb": None,
            "pe_ttm": 9.2,
            "pb_mrq": "1.1",
        }
    )

    assert values["legacy_id"] == str(document_id)
    assert values["payload"]["_id"] == str(document_id)
    assert values["code"] == "000001"
    assert values["source"] == "tushare"
    assert values["list_date"] == date(1991, 4, 3)
    assert values["total_mv"] == Decimal("123.45")
    assert values["circ_mv"] == Decimal("100")
    assert values["pe"] == Decimal("8.1")
    assert values["pb"] is None


def test_stock_basic_info_mapper_generates_stable_legacy_id_without_postgres_id():
    values = map_stock_basic_info({"code": "000001", "source": "tushare"})

    assert values["legacy_id"] == "stock_basic_info:tushare:000001"


def test_market_quote_mapper_splits_screening_fields():
    values = map_market_quote(
        {
            "legacy_id": "quote-1",
            "code": "000001",
            "source": "akshare",
            "trade_date": "2026-06-03",
            "open": "10.1",
            "high": "10.5",
            "low": "9.9",
            "close": "10.2",
            "pre_close": "10.0",
            "pct_chg": "2.0",
            "amount": "1000000.25",
            "volume": "300",
        }
    )

    assert values["legacy_id"] == "quote-1"
    assert values["trade_date"] == date(2026, 6, 3)
    assert values["pct_chg"] == Decimal("2.0")
    assert values["amount"] == Decimal("1000000.25")


def test_market_quote_mapper_generates_stable_legacy_id_without_postgres_id():
    values = map_market_quote({"code": "000001", "source": "akshare"})

    assert values["legacy_id"] == "market_quotes:akshare:000001"


def test_stock_daily_quote_mapper_splits_history_business_key_and_metrics():
    values = map_stock_daily_quote(
        {
            "symbol": "000001",
            "code": "000001",
            "full_symbol": "000001.SZ",
            "market": "CN",
            "trade_date": "20260603",
            "period": "daily",
            "data_source": "tushare",
            "open": "10.1",
            "close": "10.3",
            "volume": "100000",
            "amount": "123456.78",
            "change": "0.2",
            "pct_chg": "1.98",
        }
    )

    assert values["legacy_id"] == "stock_daily_quotes:tushare:000001:2026-06-03:daily"
    assert values["symbol"] == "000001"
    assert values["trade_date"] == date(2026, 6, 3)
    assert values["data_source"] == "tushare"
    assert values["period"] == "daily"
    assert values["close"] == Decimal("10.3")
    assert values["volume"] == Decimal("100000")
    assert values["deleted"] is False


def test_financial_data_mapper_splits_report_fields():
    values = map_stock_financial_data(
        {
            "legacy_id": "financial-1",
            "code": "000001",
            "data_source": "tushare",
            "report_period": "2025Q4",
            "roe": "12.3",
            "roa": "1.2",
            "netprofit_margin": "18.9",
            "gross_margin": "44.1",
        }
    )

    assert values["legacy_id"] == "financial-1"
    assert values["report_period"] == "2025Q4"
    assert values["roe"] == Decimal("12.3")
    assert values["gross_margin"] == Decimal("44.1")


def test_financial_data_mapper_generates_stable_legacy_id_without_postgres_id():
    values = map_stock_financial_data(
        {"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}
    )

    assert values["legacy_id"] == "stock_financial_data:tushare:000001:2025Q4"


def test_stock_news_mapper_generates_stable_legacy_id_and_splits_query_fields():
    values = map_stock_news(
        {
            "symbol": "000001",
            "market": "CN",
            "title": "平安银行新闻",
            "url": "https://example.com/news/1",
            "publish_time": "2026-06-03T10:00:00",
            "data_source": "akshare",
            "category": "company",
            "sentiment": "positive",
            "importance": "high",
        }
    )

    assert values["legacy_id"].startswith("stock_news:")
    assert values["symbol"] == "000001"
    assert values["data_source"] == "akshare"
    assert values["publish_time"].isoformat() == "2026-06-03T10:00:00"
    assert values["deleted"] is False


def test_analysis_task_mapper_splits_status_fields():
    values = map_analysis_task(
        {
            "task_id": "task-1",
            "user": "user-1",
            "stock_symbol": "000001",
            "status": "running",
            "progress": "42",
        }
    )

    assert values["legacy_id"] == "analysis_tasks:task-1"
    assert values["task_id"] == "task-1"
    assert values["user_id"] == "user-1"
    assert values["stock_symbol"] == "000001"
    assert values["progress"] == 42


def test_analysis_report_mapper_splits_report_fields():
    values = map_analysis_report(
        {
            "analysis_id": "analysis-1",
            "task_id": "task-1",
            "user": "user-1",
            "symbol": "000001",
            "analysis_date": "2026-06-03",
            "summary": "buy",
        }
    )

    assert values["legacy_id"] == "analysis_reports:analysis-1"
    assert values["analysis_id"] == "analysis-1"
    assert values["task_id"] == "task-1"
    assert values["user_id"] == "user-1"
    assert values["stock_symbol"] == "000001"
    assert values["analysis_date"] == date(2026, 6, 3)


def test_analysis_batch_and_result_mappers_split_query_fields():
    batch = map_analysis_batch(
        {
            "batch_id": "batch-1",
            "user_id": "user-1",
            "status": "pending",
            "total_tasks": "3",
        }
    )
    result = map_analysis_result(
        {
            "legacy_id": "result-1",
            "task_id": "task-1",
            "user_id": "user-1",
            "symbol": "000001",
            "status": "completed",
        }
    )

    assert batch["legacy_id"] == "analysis_batches:batch-1"
    assert batch["total_tasks"] == 3
    assert result["legacy_id"] == "result-1"
    assert result["stock_symbol"] == "000001"


def test_sync_status_mapper_splits_status_fields():
    values = map_sync_status(
        {
            "job": "example_sdk_sync",
            "status": "completed",
            "started_at": "2026-06-03T01:00:00",
            "finished_at": "2026-06-03T01:00:12",
            "duration": "12.5",
        }
    )

    assert values["legacy_id"] == "sync_status:example_sdk_sync"
    assert values["job"] == "example_sdk_sync"
    assert values["status"] == "completed"
    assert values["started_at"].isoformat() == "2026-06-03T01:00:00"
    assert values["duration"] == Decimal("12.5")


def test_sync_status_mapper_accepts_quotes_ingestion_status_shape():
    values = map_sync_status(
        {
            "job": "quotes_ingestion",
            "success": True,
            "last_sync_time": "2026-06-03T10:00:00+08:00",
            "records_count": 5440,
        }
    )

    assert values["legacy_id"] == "sync_status:quotes_ingestion"
    assert values["job"] == "quotes_ingestion"
    assert values["status"] == "success"
    assert values["finished_at"].isoformat() == "2026-06-03T10:00:00+08:00"
    assert values["payload"]["records_count"] == 5440


def test_scheduler_execution_mapper_uses_legacy_id_for_progress_updates():
    document_id = DocumentId()
    values = map_scheduler_execution(
        {
            "_id": document_id,
            "job_id": "tushare_daily",
            "status": "running",
            "progress": "66",
            "progress_message": "quotes",
            "timestamp": datetime(2026, 6, 3, 1, 0, tzinfo=timezone.utc),
            "cancel_requested": False,
        }
    )

    assert values["legacy_id"] == str(document_id)
    assert values["payload"]["_id"] == str(document_id)
    assert values["job_id"] == "tushare_daily"
    assert values["progress"] == 66
    assert values["timestamp"].isoformat() == "2026-06-03T01:00:00+00:00"
    assert values["cancel_requested"] is False


def test_scheduler_history_and_metadata_mappers_split_query_fields():
    history = map_scheduler_history(
        {
            "job_id": "daily_sync",
            "action": "trigger",
            "status": "success",
            "timestamp": "2026-06-03T11:00:00",
        }
    )
    metadata = map_scheduler_metadata(
        {
            "job_id": "daily_sync",
            "display_name": "每日同步",
            "description": "盘后同步",
        }
    )

    assert history["legacy_id"].startswith("scheduler_history:daily_sync:trigger:")
    assert history["job_id"] == "daily_sync"
    assert history["timestamp"].isoformat() == "2026-06-03T11:00:00"
    assert metadata["legacy_id"] == "scheduler_metadata:daily_sync"
    assert metadata["display_name"] == "每日同步"


def test_system_config_mapper_namespaces_keys_by_collection():
    values = map_system_config_document(
        {"provider": "dashscope", "enabled": True, "api_key": "secret"},
        collection="llm_providers",
    )

    assert values["legacy_id"] == "llm_providers:dashscope"
    assert values["config_key"] == "llm_providers:dashscope"
    assert values["config_type"] == "llm_providers"
    assert values["enabled"] is True
    assert values["payload"]["api_key"] == "secret"


def test_config_collection_select_filters_specialized_rows_by_type():
    statement = _build_specialized_select("llm_providers", SystemConfigDocument)
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "WHERE system_config_documents.config_type = " in sql
    assert statement.compile(dialect=postgresql.dialect()).params == {
        "config_type_1": "llm_providers"
    }


def test_user_favorites_mapper_flattens_embedded_favorites():
    documents = iter_user_favorite_documents(
        {
            "legacy_id": "favorites-doc-1",
            "user_id": "user-1",
            "favorites": [
                {"stock_code": "000001", "stock_name": "平安银行", "market": "A股"},
                {"stock_code": "AAPL", "stock_name": "Apple", "market": "US"},
            ],
        }
    )

    assert [document["stock_code"] for document in documents] == ["000001", "AAPL"]
    values = map_user_favorite(documents[0])
    assert values["legacy_id"] == "user_favorites:user-1:000001"
    assert values["user_id"] == "user-1"
    assert values["stock_code"] == "000001"
    assert values["deleted"] is False


def test_user_tag_mapper_uses_postgres_id_as_legacy_id():
    document_id = DocumentId()
    values = map_user_tag(
        {
            "_id": document_id,
            "user_id": "user-1",
            "name": "关注",
            "color": "#409EFF",
            "sort_order": 2,
        }
    )

    assert values["legacy_id"] == str(document_id)
    assert values["tag_id"] == str(document_id)
    assert values["name"] == "关注"
    assert values["sort_order"] == 2


def test_user_session_mapper_splits_ttl_and_audit_fields():
    document_id = DocumentId()
    values = map_user_session(
        {
            "_id": document_id,
            "session_id": "sess-1",
            "user_id": "user-1",
            "username": "admin",
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "expires_at": "2026-06-04T00:00:00",
            "last_activity": "2026-06-03T23:00:00",
        }
    )

    assert values["legacy_id"] == str(document_id)
    assert values["session_id"] == "sess-1"
    assert values["user_id"] == "user-1"
    assert values["ip_address"] == "127.0.0.1"
    assert values["expires_at"].isoformat() == "2026-06-04T00:00:00"
    assert values["last_activity_at"].isoformat() == "2026-06-03T23:00:00"
    assert values["deleted"] is False


def test_login_attempt_mapper_splits_security_audit_fields():
    values = map_login_attempt(
        {
            "username": "admin",
            "ip_address": "127.0.0.1",
            "success": False,
            "failure_reason": "bad_password",
            "timestamp": "2026-06-03T22:00:00",
        }
    )

    assert values["legacy_id"].startswith("login_attempts:")
    assert values["username"] == "admin"
    assert values["ip_address"] == "127.0.0.1"
    assert values["success"] is False
    assert values["reason"] == "bad_password"
    assert values["timestamp"].isoformat() == "2026-06-03T22:00:00"


def test_paper_mappers_split_trading_keys():
    account = map_paper_account({"user_id": "user-1", "cash": {"USD": 1000}})
    position = map_paper_position(
        {
            "user_id": "user-1",
            "code": "AAPL",
            "market": "US",
            "currency": "USD",
            "quantity": 3,
        }
    )
    order = map_paper_order(
        {
            "legacy_id": "order-1",
            "user_id": "user-1",
            "code": "AAPL",
            "side": "buy",
            "status": "filled",
        }
    )
    trade = map_paper_trade(
        {
            "legacy_id": "trade-1",
            "user_id": "user-1",
            "code": "AAPL",
            "side": "buy",
            "timestamp": "2026-06-03T01:00:00",
        }
    )

    assert account["legacy_id"] == "paper_accounts:user-1"
    assert position["legacy_id"] == "paper_positions:user-1:AAPL"
    assert position["quantity"] == 3
    assert order["legacy_id"] == "order-1"
    assert trade["timestamp"].isoformat() == "2026-06-03T01:00:00"


def test_user_account_mapper_splits_auth_fields():
    document_id = DocumentId()
    values = map_user_account(
        {
            "_id": document_id,
            "username": "admin",
            "email": "admin@example.com",
            "is_active": True,
            "is_admin": True,
        }
    )

    assert values["legacy_id"] == str(document_id)
    assert values["username"] == "admin"
    assert values["email"] == "admin@example.com"
    assert values["is_active"] is True
    assert values["is_admin"] is True


def test_operational_mappers_split_log_and_backup_fields():
    log_id = DocumentId()
    backup_id = DocumentId()
    log_values = map_operation_log(
        {
            "_id": log_id,
            "user_id": "user-1",
            "username": "admin",
            "action_type": "user_login",
            "success": True,
            "timestamp": "2026-06-03T01:00:00",
        }
    )
    backup_values = map_database_backup(
        {
            "_id": backup_id,
            "name": "daily",
            "filename": "backup.gz",
            "created_by": "admin",
            "backup_type": "postgres_document_json",
        }
    )

    assert log_values["legacy_id"] == str(log_id)
    assert log_values["action_type"] == "user_login"
    assert log_values["timestamp"].isoformat() == "2026-06-03T01:00:00"
    assert backup_values["legacy_id"] == str(backup_id)
    assert backup_values["filename"] == "backup.gz"


def test_dynamic_business_mappers_split_query_fields():
    notification_id = DocumentId()
    notification = map_notification(
        {
            "_id": notification_id,
            "user_id": "user-1",
            "type": "analysis",
            "status": "unread",
            "severity": "info",
            "title": "分析完成",
        }
    )
    usage = map_token_usage(
        {
            "provider": "dashscope",
            "model_name": "qwen-plus",
            "session_id": "session-1",
            "timestamp": "2026-06-03T10:00:00",
            "input_tokens": "10",
            "output_tokens": 20,
            "cost": "0.12345678",
            "currency": "CNY",
        }
    )
    internal = map_internal_message(
        {
            "message_id": "msg-1",
            "symbol": "000001",
            "message_type": "research_report",
            "category": "fundamental_analysis",
            "source": {"type": "internal_research", "department": "研究部"},
            "related_data": {"rating": "buy"},
            "confidence_level": "0.8",
            "created_time": "2026-06-03T11:00:00",
        }
    )
    social = map_social_media_message(
        {
            "message_id": "social-1",
            "platform": "weibo",
            "symbol": "000001",
            "message_type": "post",
            "sentiment": "positive",
            "importance": "high",
            "publish_time": "2026-06-03T12:00:00",
            "author": {"influence_score": "1.5", "verified": True},
            "engagement": {"engagement_rate": "0.12"},
        }
    )

    assert notification["legacy_id"] == str(notification_id)
    assert notification["user_id"] == "user-1"
    assert usage["legacy_id"].startswith("token_usage:")
    assert usage["input_tokens"] == 10
    assert usage["cost"] == Decimal("0.12345678")
    assert internal["legacy_id"] == "internal_messages:msg-1"
    assert internal["department"] == "研究部"
    assert social["legacy_id"] == "social_media_messages:weibo:social-1"
    assert social["verified"] is True
