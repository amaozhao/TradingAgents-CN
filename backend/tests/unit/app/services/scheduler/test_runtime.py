from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import database
from app.services.scheduler import runtime as runtime_module
from app.services.scheduler.common import TaskCancelledException


class FakeSchedulerExecutions:
    def __init__(self, document: dict[str, Any] | None) -> None:
        self.document = document
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.inserts: list[dict[str, Any]] = []

    async def find_one(self, *_args: Any, **_kwargs: Any) -> dict[str, Any] | None:
        return self.document

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        self.updates.append((query, update))
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def insert_one(self, document: dict[str, Any]):
        self.inserts.append(document)
        return SimpleNamespace(inserted_id="new-execution")


class FakeDb:
    def __init__(self, document: dict[str, Any] | None) -> None:
        self.scheduler_executions = FakeSchedulerExecutions(document)


@pytest.mark.asyncio
async def test_update_job_progress_uses_async_database(monkeypatch):
    sync_calls: list[None] = []
    db = FakeDb(
        {
            "_id": "execution-1",
            "job_id": "job-1",
            "status": "running",
        }
    )

    monkeypatch.setattr(database, "get_postgres_db_sync", lambda: sync_calls.append(None))
    monkeypatch.setattr(runtime_module, "get_postgres_db", lambda: db, raising=False)

    await runtime_module.update_job_progress("job-1", 42, message="running")

    assert sync_calls == []
    assert db.scheduler_executions.updates[0][0] == {"_id": "execution-1"}
    assert db.scheduler_executions.updates[0][1]["$set"]["progress"] == 42
    assert db.scheduler_executions.updates[0][1]["$set"]["progress_message"] == "running"


@pytest.mark.asyncio
async def test_update_job_progress_raises_cancelled(monkeypatch):
    db = FakeDb(
        {
            "_id": "execution-1",
            "job_id": "job-1",
            "status": "running",
            "cancel_requested": True,
        }
    )

    monkeypatch.setattr(runtime_module, "get_postgres_db", lambda: db, raising=False)

    with pytest.raises(TaskCancelledException):
        await runtime_module.update_job_progress("job-1", 50)
