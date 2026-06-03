from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.services.market import news as news_data_service


@pytest.mark.asyncio
async def test_save_news_data_dual_writes_standardized_documents(monkeypatch):
    service = news_data_service.NewsDataService()
    service._collection = FakeNewsCollection()
    service._indexes_ensured = True
    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(news_data_service, "dual_write_hot_documents", fake_dual_write)

    saved = await service.save_news_data(
        {
            "symbol": "000001",
            "title": "平安银行新闻",
            "url": "https://example.com/news/1",
            "publish_time": "2026-06-03T10:00:00",
        },
        data_source="akshare",
        market="CN",
    )

    assert saved == 1
    assert dual_write_calls[0][0] == "stock_news"
    assert dual_write_calls[0][1][0]["symbol"] == "000001"
    assert dual_write_calls[0][1][0]["data_source"] == "akshare"
    assert dual_write_calls[0][1][0]["market"] == "CN"


@pytest.mark.asyncio
async def test_delete_old_news_dual_writes_tombstones(monkeypatch):
    existing = [
        {
            "_id": ObjectId(),
            "symbol": "000001",
            "title": "旧新闻",
            "url": "https://example.com/news/old",
        }
    ]
    service = news_data_service.NewsDataService()
    service._collection = FakeNewsCollection(existing=existing)
    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(news_data_service, "dual_write_hot_documents", fake_dual_write)

    deleted = await service.delete_old_news(days_to_keep=90)

    assert deleted == 1
    assert dual_write_calls[0][0] == "stock_news"
    assert dual_write_calls[0][1][0]["_id"] == existing[0]["_id"]
    assert dual_write_calls[0][1][0]["deleted"] is True


class FakeNewsCollection:
    def __init__(self, existing=None):
        self.existing = existing or []

    async def create_index(self, *_args, **_kwargs):
        return None

    async def bulk_write(self, operations):
        self.operations = operations
        return SimpleNamespace(upserted_count=len(operations), modified_count=0)

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.existing)

    async def delete_many(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=len(self.existing))


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return self.documents
