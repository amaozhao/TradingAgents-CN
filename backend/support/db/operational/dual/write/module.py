from types import SimpleNamespace
import json

import pytest
from bson import ObjectId

from app.models.operations import ActionType, OperationLogCreate
from app.services import operation as operation_log_service
from app.services.database import backup


@pytest.mark.asyncio
async def test_create_operation_log_dual_writes_inserted_document(monkeypatch):
    service = operation_log_service.OperationLogService()
    collection = FakeAsyncCollection()
    db = FakeMongoDB({"operation_logs": collection})
    dual_write_calls = []

    async def fake_dual_write(collection_name, document):
        dual_write_calls.append((collection_name, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(operation_log_service, "get_mongo_db", lambda: db)
    monkeypatch.setattr(operation_log_service, "dual_write_hot_document", fake_dual_write)

    log_id = await service.create_log(
        "user-1",
        "admin",
        OperationLogCreate(
            action_type=ActionType.USER_LOGIN,
            action="用户登录",
            success=True,
        ),
    )

    assert log_id == str(collection.inserted_id)
    assert dual_write_calls[0][0] == "operation_logs"
    assert dual_write_calls[0][1]["_id"] == collection.inserted_id
    assert dual_write_calls[0][1]["user_id"] == "user-1"
    assert dual_write_calls[0][1]["username"] == "admin"


@pytest.mark.asyncio
async def test_clear_operation_logs_dual_writes_tombstones(monkeypatch):
    service = operation_log_service.OperationLogService()
    existing = [{"_id": ObjectId(), "user_id": "user-1", "action_type": "login"}]
    db = FakeMongoDB({"operation_logs": FakeAsyncCollection(existing=existing)})
    dual_write_calls = []

    async def fake_dual_write_many(collection_name, documents):
        dual_write_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(operation_log_service, "get_mongo_db", lambda: db)
    monkeypatch.setattr(operation_log_service, "dual_write_hot_documents", fake_dual_write_many)

    result = await service.clear_logs(action_type="login")

    assert result["deleted_count"] == 1
    assert dual_write_calls[0][0] == "operation_logs"
    assert dual_write_calls[0][1][0]["_id"] == existing[0]["_id"]
    assert dual_write_calls[0][1][0]["deleted"] is True


@pytest.mark.asyncio
async def test_delete_database_backup_dual_writes_tombstone(monkeypatch):
    backup_id = ObjectId()
    backup_document = {
        "_id": backup_id,
        "name": "daily",
        "filename": "backup.json.gz",
        "file_path": "/tmp/non-existent-backup.json.gz",
        "size": 1,
        "collections": ["operation_logs"],
        "created_by": "user-1",
    }
    db = SimpleNamespace(database_backups=FakeAsyncCollection(existing=[backup_document]))
    dual_write_calls = []

    async def fake_dual_write(collection_name, document):
        dual_write_calls.append((collection_name, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(backup, "get_mongo_db", lambda: db)
    monkeypatch.setattr(backup, "dual_write_hot_document", fake_dual_write)
    monkeypatch.setattr(backup.os.path, "exists", lambda _path: False)

    await backup.delete_backup(str(backup_id))

    assert dual_write_calls[0][0] == "database_backups"
    assert dual_write_calls[0][1]["_id"] == backup_id
    assert dual_write_calls[0][1]["deleted"] is True


@pytest.mark.asyncio
async def test_import_supported_collection_dual_writes_tombstones_and_inserted_docs(monkeypatch):
    existing = [{"_id": ObjectId(), "code": "000001", "source": "tushare"}]
    collection = FakeAsyncCollection(existing=existing)
    db = FakeMongoDB({"stock_basic_info": collection})
    dual_write_calls = []

    async def fake_dual_write_many(collection_name, documents):
        dual_write_calls.append((collection_name, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(backup, "get_mongo_db", lambda: db)
    monkeypatch.setattr(backup, "dual_write_hot_documents", fake_dual_write_many)

    result = await backup.import_data(
        json.dumps([{"code": "000002", "source": "tushare"}]).encode("utf-8"),
        "stock_basic_info",
        overwrite=True,
    )

    assert result["inserted_count"] == 1
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert dual_write_calls[0][1][0]["_id"] == existing[0]["_id"]
    assert dual_write_calls[0][1][0]["deleted"] is True
    assert dual_write_calls[1][0] == "stock_basic_info"
    assert dual_write_calls[1][1][0]["code"] == "000002"


@pytest.mark.asyncio
async def test_import_unknown_collection_records_mongo_only(monkeypatch):
    db = FakeMongoDB({"ad_hoc_collection": FakeAsyncCollection()})
    mongo_only_calls = []

    monkeypatch.setattr(backup, "get_mongo_db", lambda: db)
    monkeypatch.setattr(
        backup,
        "log_mongo_only_write",
        lambda collection, reason: mongo_only_calls.append((collection, reason)),
    )

    result = await backup.import_data(
        json.dumps([{"value": 1}]).encode("utf-8"),
        "ad_hoc_collection",
        overwrite=False,
    )

    assert result["inserted_count"] == 1
    assert mongo_only_calls == [("ad_hoc_collection", "database_import_unsupported_collection")]


class FakeMongoDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


class FakeAsyncCollection:
    def __init__(self, existing=None):
        self.inserted_id = ObjectId()
        self.existing = existing or []

    async def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id=self.inserted_id)

    async def insert_many(self, documents):
        for document in documents:
            document.setdefault("_id", ObjectId())
        self.inserted_many = documents
        return SimpleNamespace(inserted_ids=[document["_id"] for document in documents])

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.existing)

    async def find_one(self, *_args, **_kwargs):
        return self.existing[0] if self.existing else None

    async def delete_many(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=len(self.existing))

    async def delete_one(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=1)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return self.documents
