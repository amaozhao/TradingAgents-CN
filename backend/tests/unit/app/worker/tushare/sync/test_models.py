from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core import database
from app.worker.tushare import sync as sync_module


class FakeSchedulerExecutions:
    def __init__(self) -> None:
        self.document = {
            "_id": "execution-1",
            "job_id": "job-1",
            "status": "running",
            "progress": 10,
        }
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def find_one(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return self.document

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        self.updates.append((query, update))
        return SimpleNamespace(matched_count=1, modified_count=1)


class FakeDb:
    def __init__(self) -> None:
        self.scheduler_executions = FakeSchedulerExecutions()


class ProgressOnlyService(sync_module._TushareSyncServiceMixin3):
    def __init__(self, db: FakeDb) -> None:
        self.db = db


@pytest.mark.asyncio
async def test_update_progress_uses_async_database(monkeypatch):
    sync_calls: list[None] = []
    db = FakeDb()

    monkeypatch.setattr(
        database,
        "get_postgres_db_sync",
        lambda: sync_calls.append(None),
    )

    async def dual_write(_collection: str, _document: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(sync_module, "dual_write_hot_document", dual_write)

    service = ProgressOnlyService(db)

    await service._update_progress("job-1", 42, "已处理 42%")

    assert sync_calls == []
    assert db.scheduler_executions.updates[0][0] == {"_id": "execution-1"}
    assert db.scheduler_executions.updates[0][1]["$set"]["progress"] == 42
