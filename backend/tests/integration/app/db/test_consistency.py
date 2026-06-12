import pytest

from app.db import consistency as consistency_checker
from app.db.consistency import compare_hot_collections, consistency_summary_to_dict


@pytest.mark.asyncio
async def test_compare_hot_collections_reports_consistent_counts_and_keys(monkeypatch):
    postgres_db = FakePostgreSQL(
        {
            "stock_basic_info": [{"code": "000001", "source": "tushare"}],
            "market_quotes": [{"code": "000001", "source": "akshare"}],
            "stock_daily_quotes": [
                {
                    "symbol": "000001",
                    "trade_date": "2026-06-03",
                    "data_source": "tushare",
                    "period": "daily",
                }
            ],
            "stock_financial_data": [
                {"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}
            ],
            "stock_news": [{"legacy_id": "news-1", "symbol": "000001"}],
            "analysis_tasks": [{"task_id": "task-1"}],
            "analysis_reports": [{"analysis_id": "analysis-1"}],
            "analysis_batches": [{"batch_id": "batch-1"}],
            "analysis_results": [{"legacy_id": "result-1", "task_id": "task-1"}],
            "sync_status": [{"job": "example_sdk_sync"}],
            "quotes_ingestion_status": [{"job": "quotes_ingestion", "success": True}],
            "scheduler_executions": [{"_id": "scheduler-1", "job_id": "tushare_daily"}],
            "scheduler_history": [
                {"legacy_id": "history-1", "job_id": "tushare_daily"}
            ],
            "scheduler_metadata": [
                {"job_id": "tushare_daily", "display_name": "每日同步"}
            ],
            "user_favorites": [
                {"user_id": "user-1", "favorites": [{"stock_code": "000001"}]}
            ],
            "user_tags": [{"legacy_id": "tag-1", "user_id": "user-1", "name": "关注"}],
            "paper_accounts": [{"user_id": "user-1"}],
            "paper_positions": [{"user_id": "user-1", "code": "AAPL"}],
            "paper_orders": [{"legacy_id": "order-1", "user_id": "user-1"}],
            "paper_trades": [{"legacy_id": "trade-1", "user_id": "user-1"}],
            "users": [{"username": "admin", "email": "admin@example.com"}],
            "users_collection": [{"username": "demo", "email": "demo@example.com"}],
            "user_sessions": [{"session_id": "sess-1", "user_id": "user-1"}],
            "login_attempts": [{"legacy_id": "attempt-1", "username": "admin"}],
            "operation_logs": [{"legacy_id": "log-1", "user_id": "user-1"}],
            "database_backups": [{"legacy_id": "backup-1", "name": "daily"}],
            "notifications": [{"legacy_id": "notif-1", "user_id": "user-1"}],
            "token_usage": [{"legacy_id": "usage-1", "provider": "dashscope"}],
            "internal_messages": [{"message_id": "msg-1", "symbol": "000001"}],
            "social_media_messages": [{"message_id": "social-1", "platform": "weibo"}],
        }
    )

    async def fake_postgres_count(_session, _model):
        if _model is consistency_checker.UserAccount:
            return 2
        if _model is consistency_checker.SyncStatusDocument:
            return 2
        return 1

    async def fake_postgres_keys(_session, spec, _sample_limit):
        if spec.collection == "users":
            return {("admin",), ("demo",)}
        if spec.collection == "sync_status":
            return {("example_sdk_sync",), ("quotes_ingestion",)}
        return {
            {
                "stock_basic_info": ("000001", "tushare"),
                "market_quotes": ("000001", "akshare"),
                "stock_daily_quotes": ("000001", "2026-06-03", "tushare", "daily"),
                "stock_financial_data": ("000001", "tushare", "2025Q4"),
                "stock_news": ("news-1",),
                "analysis_tasks": ("task-1",),
                "analysis_reports": ("analysis-1",),
                "analysis_batches": ("batch-1",),
                "analysis_results": ("result-1",),
                "scheduler_executions": ("scheduler-1",),
                "scheduler_history": ("history-1",),
                "scheduler_metadata": ("tushare_daily",),
                "user_favorites": ("user-1", "000001"),
                "user_tags": ("tag-1",),
                "paper_accounts": ("user-1",),
                "paper_positions": ("user-1", "AAPL"),
                "paper_orders": ("order-1",),
                "paper_trades": ("trade-1",),
                "user_sessions": ("sess-1",),
                "login_attempts": ("attempt-1",),
                "operation_logs": ("log-1",),
                "database_backups": ("backup-1",),
                "notifications": ("notif-1",),
                "token_usage": ("usage-1",),
                "internal_messages": ("msg-1",),
                "social_media_messages": ("social-1", "weibo"),
            }[spec.collection]
        }

    monkeypatch.setattr(consistency_checker, "_table_count", fake_postgres_count)
    monkeypatch.setattr(consistency_checker, "_table_business_keys", fake_postgres_keys)

    results = await compare_hot_collections(
        postgres_db, lambda: FakeSession(), sample_limit=10
    )
    summary = consistency_summary_to_dict(results)

    assert summary["all_consistent"] is True
    assert summary["collections"]["stock_basic_info"]["count_delta"] == 0
    assert summary["collections"]["sync_status"]["postgres_count"] == 2


@pytest.mark.asyncio
async def test_compare_hot_collections_reports_missing_postgres_keys(monkeypatch):
    postgres_db = FakePostgreSQL(
        {
            "stock_basic_info": [{"code": "000001", "source": "tushare"}],
            "market_quotes": [],
            "stock_daily_quotes": [],
            "stock_financial_data": [],
            "stock_news": [],
            "analysis_tasks": [],
            "analysis_reports": [],
            "analysis_batches": [],
            "analysis_results": [],
            "sync_status": [],
            "quotes_ingestion_status": [],
            "scheduler_executions": [],
            "scheduler_history": [],
            "scheduler_metadata": [],
            "user_favorites": [],
            "user_tags": [],
            "paper_accounts": [],
            "paper_positions": [],
            "paper_orders": [],
            "paper_trades": [],
            "users": [],
            "user_sessions": [],
            "login_attempts": [],
            "operation_logs": [],
            "database_backups": [],
            "notifications": [],
            "token_usage": [],
            "internal_messages": [],
            "social_media_messages": [],
        }
    )

    async def fake_postgres_count(_session, model):
        return 0 if model is consistency_checker.StockBasicInfo else 0

    async def fake_postgres_keys(_session, _spec, _sample_limit):
        return set()

    monkeypatch.setattr(consistency_checker, "_table_count", fake_postgres_count)
    monkeypatch.setattr(consistency_checker, "_table_business_keys", fake_postgres_keys)

    results = await compare_hot_collections(
        postgres_db, lambda: FakeSession(), sample_limit=10
    )
    summary = consistency_summary_to_dict(results)

    assert summary["all_consistent"] is False
    assert summary["collections"]["stock_basic_info"]["count_delta"] == -1
    assert summary["collections"]["stock_basic_info"]["missing_in_postgres"] == [
        ("000001", "tushare")
    ]


class FakePostgreSQL:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return FakePostgreSQLCollection(self.collections.get(name, []))


class FakePostgreSQLCollection:
    def __init__(self, documents):
        self.documents = documents

    async def count_documents(self, _query):
        return len(self.documents)

    def find(self, _query):
        return FakeCursor(self.documents)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def limit(self, _limit):
        return self

    def __aiter__(self):
        self._iterator = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None
