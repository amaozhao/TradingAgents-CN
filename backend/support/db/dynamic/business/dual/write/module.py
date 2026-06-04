from types import SimpleNamespace

import pandas as pd
import pytest

from app.db.ids import DocumentId
from app.schemas.config import UsageRecord
from app.schemas.notification import NotificationCreate
from app.services import (
    historical_data_service,
    internal_message_service,
    notifications_service,
    social_media_service,
    usage_statistics_service,
)


@pytest.mark.asyncio
async def test_notification_create_and_mark_read_dual_write(monkeypatch):
    service = notifications_service.NotificationsService()
    collection = FakeCollection(count=1)
    db = FakeDB({"notifications": collection})
    single_calls = []

    async def fake_dual_write(collection_name, document):
        single_calls.append((collection_name, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(notifications_service, "get_postgres_db", lambda: db)
    monkeypatch.setattr(
        notifications_service, "dual_write_hot_document", fake_dual_write
    )

    notification_id = await service.create_and_publish(
        NotificationCreate(user_id="user-1", type="analysis", title="分析完成")
    )
    assert notification_id == str(collection.inserted_id)

    assert await service.mark_read("user-1", notification_id) is True

    assert single_calls[0][0] == "notifications"
    assert single_calls[0][1]["_id"] == collection.inserted_id
    assert single_calls[1][0] == "notifications"
    assert single_calls[1][1]["status"] == "read"


@pytest.mark.asyncio
async def test_usage_statistics_add_and_delete_dual_write(monkeypatch):
    service = usage_statistics_service.UsageStatisticsService()
    collection = FakeCollection(
        existing=[{"_id": DocumentId(), "provider": "dashscope"}]
    )
    db = FakeDB({"token_usage": collection})
    single_calls = []
    batch_calls = []

    async def fake_dual_write(collection_name, document):
        single_calls.append((collection_name, document))
        return SimpleNamespace(status="written", reason="")

    async def fake_dual_write_many(collection_name, documents):
        batch_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(usage_statistics_service, "get_postgres_db", lambda: db)
    monkeypatch.setattr(
        usage_statistics_service, "dual_write_hot_document", fake_dual_write
    )
    monkeypatch.setattr(
        usage_statistics_service, "dual_write_hot_documents", fake_dual_write_many
    )

    assert (
        await service.add_usage_record(
            UsageRecord(
                timestamp="2026-06-03T10:00:00",
                provider="dashscope",
                model_name="qwen-plus",
                input_tokens=10,
                output_tokens=20,
                cost=0.1,
                session_id="session-1",
            )
        )
        is True
    )
    assert await service.delete_old_records(days=90) == 1

    assert single_calls[0][0] == "token_usage"
    assert single_calls[0][1]["_id"] == collection.inserted_id
    assert batch_calls[0][0] == "token_usage"
    assert batch_calls[0][1][0]["deleted"] is True


@pytest.mark.asyncio
async def test_internal_messages_dual_write_bulk_upserts(monkeypatch):
    service = internal_message_service.InternalMessageService()
    service.collection = FakeCollection()
    batch_calls = []

    async def fake_dual_write_many(collection_name, documents):
        batch_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(
        internal_message_service, "dual_write_hot_documents", fake_dual_write_many
    )

    result = await service.save_internal_messages(
        [{"message_id": "msg-1", "symbol": "000001", "message_type": "research_report"}]
    )

    assert result["saved"] == 1
    assert batch_calls[0][0] == "internal_messages"
    assert batch_calls[0][1][0]["message_id"] == "msg-1"


@pytest.mark.asyncio
async def test_social_media_messages_dual_write_bulk_upserts(monkeypatch):
    service = social_media_service.SocialMediaService()
    service.collection = FakeCollection()
    batch_calls = []

    async def fake_dual_write_many(collection_name, documents):
        batch_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(
        social_media_service, "dual_write_hot_documents", fake_dual_write_many
    )

    result = await service.save_social_media_messages(
        [{"message_id": "social-1", "platform": "weibo", "symbol": "000001"}]
    )

    assert result["saved"] == 1
    assert batch_calls[0][0] == "social_media_messages"
    assert batch_calls[0][1][0]["message_id"] == "social-1"
    assert batch_calls[0][1][0]["platform"] == "weibo"


@pytest.mark.asyncio
async def test_historical_data_service_dual_writes_standardized_daily_quotes(
    monkeypatch,
):
    service = historical_data_service.HistoricalDataService()
    service.collection = FakeCollection()
    batch_calls = []

    async def fake_dual_write_many(collection_name, documents):
        batch_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(
        historical_data_service, "dual_write_hot_documents", fake_dual_write_many
    )

    saved = await service.save_historical_data(
        symbol="000001",
        data=pd.DataFrame(
            [
                {
                    "trade_date": "20260603",
                    "open": 10.1,
                    "close": 10.3,
                    "volume": 100,
                    "amount": 200,
                }
            ],
        ),
        data_source="tushare",
        market="CN",
        period="daily",
    )

    assert saved == 1
    assert batch_calls[0][0] == "stock_daily_quotes"
    assert batch_calls[0][1][0]["symbol"] == "000001"
    assert batch_calls[0][1][0]["trade_date"] == "2026-06-03"
    assert batch_calls[0][1][0]["data_source"] == "tushare"
    assert batch_calls[0][1][0]["period"] == "daily"


class FakeDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


class FakeCollection:
    def __init__(self, existing=None, count=0):
        self.inserted_id = DocumentId()
        self.existing = existing or []
        self.count = count

    async def create_index(self, *_args, **_kwargs):
        return None

    async def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id=self.inserted_id)

    async def bulk_write(self, operations, **_kwargs):
        self.operations = operations
        return SimpleNamespace(upserted_count=len(operations), modified_count=0)

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.existing)

    async def count_documents(self, *_args, **_kwargs):
        return self.count

    async def delete_many(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=len(self.existing))

    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(modified_count=1)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self.documents
