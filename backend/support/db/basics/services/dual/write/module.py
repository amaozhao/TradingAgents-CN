from types import SimpleNamespace

import pytest

from app.core import database as database_module
from app.routers import sources
from app.services.sync import basic as basics_sync_service
from app.services.sync import source as multi_source_basics_sync_service


@pytest.mark.asyncio
async def test_basics_sync_status_dual_writes_postgres(monkeypatch):
    service = basics_sync_service.BasicsSyncService()
    fake_db = FakeDatabase()
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document.copy()))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(basics_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._persist_status(fake_db, {"status": "running", "total": 10})

    assert fake_db.sync_status.updates[0][0] == {"job": "stock_basics"}
    assert dual_write_calls == [
        ("sync_status", {"status": "running", "total": 10, "job": "stock_basics"})
    ]


@pytest.mark.asyncio
async def test_basics_sync_bulk_dual_writes_stock_basic_info(monkeypatch):
    service = basics_sync_service.BasicsSyncService()
    fake_db = FakeDatabase()
    dual_write_calls = []
    documents = [{"code": "000001", "source": "tushare", "name": "Ping An"}]

    async def fake_dual_write_many(collection, docs):
        dual_write_calls.append((collection, [doc.copy() for doc in docs]))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(basics_sync_service, "dual_write_hot_documents", fake_dual_write_many)

    inserted, updated = await service._execute_bulk_write_with_retry(
        fake_db,
        [object()],
        documents,
    )

    assert (inserted, updated) == (1, 1)
    assert len(fake_db.stock_basic_info.bulk_writes[0][0]) == 1
    assert dual_write_calls == [("stock_basic_info", documents)]


@pytest.mark.asyncio
async def test_multi_source_basics_status_dual_writes_postgres(monkeypatch):
    service = multi_source_basics_sync_service.MultiSourceBasicsSyncService()
    fake_db = FakeDatabase()
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document.copy()))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(multi_source_basics_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._persist_status(
        fake_db,
        {"data_type": "stock_basics", "status": "running"},
    )

    assert fake_db.sync_status.updates[0][0] == {
        "data_type": "stock_basics",
        "job": "stock_basics_multi_source",
    }
    assert dual_write_calls == [
        (
            "sync_status",
            {
                "data_type": "stock_basics",
                "status": "running",
                "job": "stock_basics_multi_source",
            },
        )
    ]


@pytest.mark.asyncio
async def test_multi_source_basics_bulk_dual_writes_stock_basic_info(monkeypatch):
    service = multi_source_basics_sync_service.MultiSourceBasicsSyncService()
    fake_db = FakeDatabase()
    dual_write_calls = []
    documents = [{"code": "000001", "source": "akshare", "name": "Ping An"}]

    async def fake_dual_write_many(collection, docs):
        dual_write_calls.append((collection, [doc.copy() for doc in docs]))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(multi_source_basics_sync_service, "dual_write_hot_documents", fake_dual_write_many)

    inserted, updated = await service._execute_bulk_write_with_retry(
        fake_db,
        [object()],
        documents,
    )

    assert (inserted, updated) == (1, 1)
    assert len(fake_db.stock_basic_info.bulk_writes[0][0]) == 1
    assert dual_write_calls == [("stock_basic_info", documents)]


@pytest.mark.asyncio
async def test_clear_multi_source_cache_dual_writes_cleared_status(monkeypatch):
    fake_db = SimpleNamespace(sync_status=FakeDeleteManyCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document.copy()))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(database_module, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(
        multi_source_sync,
        "get_multi_source_sync_service",
        lambda: SimpleNamespace(_running=True),
    )
    monkeypatch.setattr(multi_source_sync, "DataSourceManager", lambda: SimpleNamespace())
    monkeypatch.setattr(multi_source_sync, "dual_write_hot_document", fake_dual_write)

    response = await multi_source_sync.clear_sync_cache()

    assert response.success is True
    assert fake_db.sync_status.deleted_queries == [{"job": "stock_basics_multi_source"}]
    assert dual_write_calls[0][0] == "sync_status"
    assert dual_write_calls[0][1]["job"] == "stock_basics_multi_source"
    assert dual_write_calls[0][1]["status"] == "cleared"
    assert dual_write_calls[0][1]["deleted"] is True


class FakeDatabase:
    def __init__(self):
        self.sync_status = FakeUpdateCollection()
        self.stock_basic_info = FakeBulkCollection()

    def __getitem__(self, name):
        return getattr(self, name)


class FakeUpdateCollection:
    def __init__(self):
        self.updates = []

    async def update_one(self, *args, **kwargs):
        self.updates.append((args[0], args[1], kwargs))
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)


class FakeBulkCollection:
    def __init__(self):
        self.bulk_writes = []

    async def bulk_write(self, *args, **kwargs):
        self.bulk_writes.append((args[0], kwargs))
        return SimpleNamespace(upserted_ids={0: "mongo-id"}, upserted_count=1, modified_count=1)


class FakeDeleteManyCollection:
    def __init__(self):
        self.deleted_queries = []

    async def delete_many(self, query):
        self.deleted_queries.append(query)
        return SimpleNamespace(deleted_count=1)
