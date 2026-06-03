import pytest

from app.db.migrate import (
    HOT_COLLECTIONS,
    migrate_hot_collections,
)


@pytest.mark.asyncio
async def test_migrate_hot_collections_batches_commits_and_reports_counts():
    mongo_db = FakeMongoDB(
        {
            "stock_basic_info": [
                {"code": "000001", "source": "tushare"},
                {"code": "000002", "source": "tushare"},
            ],
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
            "stock_news": [
                {
                    "symbol": "000001",
                    "title": "平安银行新闻",
                    "url": "https://example.com/news/1",
                    "publish_time": "2026-06-03T10:00:00",
                }
            ],
            "analysis_tasks": [{"task_id": "task-1", "status": "running"}],
            "analysis_reports": [{"analysis_id": "analysis-1", "summary": "buy"}],
            "analysis_batches": [{"batch_id": "batch-1", "user_id": "user-1"}],
            "analysis_results": [{"legacy_id": "result-1", "task_id": "task-1"}],
            "sync_status": [{"job": "example_sdk_sync", "status": "completed"}],
            "quotes_ingestion_status": [{"job": "quotes_ingestion", "success": True}],
            "scheduler_executions": [{"legacy_id": "scheduler-1", "job_id": "tushare_daily"}],
            "scheduler_history": [{"job_id": "tushare_daily", "action": "trigger"}],
            "scheduler_metadata": [{"job_id": "tushare_daily", "display_name": "每日同步"}],
            "system_configs": [{"name": "active", "is_active": True}],
            "llm_providers": [{"provider": "dashscope", "enabled": True}],
            "model_catalog": [{"provider": "dashscope", "models": []}],
            "market_categories": [{"id": "a_shares", "enabled": True}],
            "datasource_groupings": [{"id": "akshare_a", "enabled": True}],
            "user_favorites": [
                {
                    "user_id": "user-1",
                    "favorites": [
                        {"stock_code": "000001", "stock_name": "平安银行"},
                        {"stock_code": "AAPL", "stock_name": "Apple"},
                    ],
                }
            ],
            "user_tags": [{"legacy_id": "tag-1", "user_id": "user-1", "name": "关注"}],
            "paper_accounts": [{"user_id": "user-1"}],
            "paper_positions": [{"user_id": "user-1", "code": "AAPL"}],
            "paper_orders": [{"legacy_id": "order-1", "user_id": "user-1"}],
            "paper_trades": [{"legacy_id": "trade-1", "user_id": "user-1"}],
            "users": [{"username": "admin", "email": "admin@example.com"}],
            "users_collection": [{"username": "demo", "email": "demo@example.com"}],
            "user_sessions": [
                {"session_id": "sess-1", "user_id": "user-1", "expires_at": "2026-06-04T00:00:00"}
            ],
            "login_attempts": [
                {"legacy_id": "attempt-1", "username": "admin", "success": False}
            ],
            "operation_logs": [{"legacy_id": "log-1", "user_id": "user-1"}],
            "database_backups": [{"legacy_id": "backup-1", "name": "daily"}],
            "notifications": [{"legacy_id": "notif-1", "user_id": "user-1"}],
            "token_usage": [{"legacy_id": "usage-1", "provider": "dashscope"}],
            "internal_messages": [{"message_id": "msg-1", "symbol": "000001"}],
            "social_media_messages": [{"message_id": "social-1", "platform": "weibo"}],
        }
    )
    session = FakeSession()

    summary = await migrate_hot_collections(mongo_db, lambda: session, batch_size=2)

    assert summary == {
        "stock_basic_info": {"migrated": 2, "commits": 1},
        "market_quotes": {"migrated": 1, "commits": 1},
        "stock_daily_quotes": {"migrated": 1, "commits": 1},
        "stock_financial_data": {"migrated": 1, "commits": 1},
        "stock_news": {"migrated": 1, "commits": 1},
        "analysis_tasks": {"migrated": 1, "commits": 1},
        "analysis_reports": {"migrated": 1, "commits": 1},
        "analysis_batches": {"migrated": 1, "commits": 1},
        "analysis_results": {"migrated": 1, "commits": 1},
        "sync_status": {"migrated": 1, "commits": 1},
        "quotes_ingestion_status": {"migrated": 1, "commits": 1},
        "scheduler_executions": {"migrated": 1, "commits": 1},
        "scheduler_history": {"migrated": 1, "commits": 1},
        "scheduler_metadata": {"migrated": 1, "commits": 1},
        "system_configs": {"migrated": 1, "commits": 1},
        "llm_providers": {"migrated": 1, "commits": 1},
        "model_catalog": {"migrated": 1, "commits": 1},
        "market_categories": {"migrated": 1, "commits": 1},
        "datasource_groupings": {"migrated": 1, "commits": 1},
        "user_favorites": {"migrated": 2, "commits": 1},
        "user_tags": {"migrated": 1, "commits": 1},
        "paper_accounts": {"migrated": 1, "commits": 1},
        "paper_positions": {"migrated": 1, "commits": 1},
        "paper_orders": {"migrated": 1, "commits": 1},
        "paper_trades": {"migrated": 1, "commits": 1},
        "users": {"migrated": 1, "commits": 1},
        "users_collection": {"migrated": 1, "commits": 1},
        "user_sessions": {"migrated": 1, "commits": 1},
        "login_attempts": {"migrated": 1, "commits": 1},
        "operation_logs": {"migrated": 1, "commits": 1},
        "database_backups": {"migrated": 1, "commits": 1},
        "notifications": {"migrated": 1, "commits": 1},
        "token_usage": {"migrated": 1, "commits": 1},
        "internal_messages": {"migrated": 1, "commits": 1},
        "social_media_messages": {"migrated": 1, "commits": 1},
    }
    assert len(session.executed) == 37
    assert session.commits == 35
    assert all(collection in HOT_COLLECTIONS for collection in summary)


class FakeMongoDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return FakeCollection(self.collections.get(name, []))


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, _query):
        return FakeCursor(self.documents)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def batch_size(self, _batch_size):
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
    def __init__(self):
        self.executed = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

from support.registry import export_module as _export_module
_export_module(globals(), "support.migration.docs.integrity.module")
_export_module(globals(), "support.postgres.local.cutover.verify.module")
del _export_module
