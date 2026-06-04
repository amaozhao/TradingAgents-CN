from types import SimpleNamespace

import pytest

from app.db.ids import DocumentId
from app.services.database import cleanup


@pytest.mark.asyncio
async def test_cleanup_analysis_results_dual_writes_analysis_tombstones(monkeypatch):
    analysis_task = {
        "_id": DocumentId(),
        "task_id": "task-1",
        "status": "completed",
    }
    analysis_result = {
        "_id": DocumentId(),
        "task_id": "task-1",
        "status": "completed",
    }
    db = SimpleNamespace(
        analysis_tasks=FakeCollection([analysis_task]),
        analysis_results=FakeCollection([analysis_result]),
    )
    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(cleanup, "get_postgres_db", lambda: db)
    monkeypatch.setattr(cleanup, "dual_write_hot_documents", fake_dual_write)

    result = await cleanup.cleanup_analysis_results(days=90)

    assert result["deleted_count"] == 2
    assert dual_write_calls[0][0] == "analysis_tasks"
    assert dual_write_calls[0][1][0]["_id"] == analysis_task["_id"]
    assert dual_write_calls[0][1][0]["deleted"] is True
    assert dual_write_calls[1][0] == "analysis_results"
    assert dual_write_calls[1][1][0]["_id"] == analysis_result["_id"]
    assert dual_write_calls[1][1][0]["deleted"] is True


@pytest.mark.asyncio
async def test_cleanup_old_data_dual_writes_session_security_tombstones(monkeypatch):
    user_session = {"_id": DocumentId(), "session_id": "sess-1", "user_id": "user-1"}
    login_attempt = {"_id": DocumentId(), "username": "admin", "success": False}
    db = SimpleNamespace(
        analysis_tasks=FakeCollection([]),
        user_sessions=FakeCollection([user_session]),
        login_attempts=FakeCollection([login_attempt]),
    )
    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(cleanup, "get_postgres_db", lambda: db)
    monkeypatch.setattr(cleanup, "dual_write_hot_documents", fake_dual_write)

    result = await cleanup.cleanup_old_data(days=90)

    assert result["deleted_count"] == 2
    assert dual_write_calls[0][0] == "user_sessions"
    assert dual_write_calls[0][1][0]["_id"] == user_session["_id"]
    assert dual_write_calls[0][1][0]["deleted"] is True
    assert dual_write_calls[1][0] == "login_attempts"
    assert dual_write_calls[1][1][0]["_id"] == login_attempt["_id"]
    assert dual_write_calls[1][1][0]["deleted"] is True


@pytest.mark.asyncio
async def test_cleanup_operation_logs_dual_writes_security_and_operation_tombstones(
    monkeypatch,
):
    user_session = {"_id": DocumentId(), "session_id": "sess-1", "user_id": "user-1"}
    login_attempt = {"_id": DocumentId(), "username": "admin", "success": False}
    operation_log = {"_id": DocumentId(), "user_id": "user-1", "action_type": "login"}
    db = SimpleNamespace(
        user_sessions=FakeCollection([user_session]),
        login_attempts=FakeCollection([login_attempt]),
        operation_logs=FakeCollection([operation_log]),
    )
    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(cleanup, "get_postgres_db", lambda: db)
    monkeypatch.setattr(cleanup, "dual_write_hot_documents", fake_dual_write)

    result = await cleanup.cleanup_operation_logs(days=90)

    assert result["deleted_count"] == 3
    assert [call[0] for call in dual_write_calls] == [
        "user_sessions",
        "login_attempts",
        "operation_logs",
    ]
    assert all(call[1][0]["deleted"] is True for call in dual_write_calls)


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.documents)

    async def delete_many(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=len(self.documents))


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return self.documents
