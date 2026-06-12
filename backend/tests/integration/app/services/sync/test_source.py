import pytest

from app.services.sync import source as sync_source
from support.registry import export_module as _export_module

_export_module(globals(), "support.sync.control.functions.module")
_export_module(globals(), "support.sync.history.fi.module")
_export_module(globals(), "support.sync.user.feedback.module")
del _export_module


@pytest.mark.asyncio
async def test_get_status_marks_stale_running_status_failed(monkeypatch):
    class FakeCollection:
        async def find_one(self, _query):
            return {
                "_id": "status-1",
                "job": sync_source.JOB_KEY,
                "data_type": "stock_basics",
                "status": "running",
                "started_at": "2026-06-04T16:03:04",
                "finished_at": None,
                "total": 0,
                "inserted": 0,
                "updated": 0,
                "errors": 0,
                "data_sources_used": [],
                "source_stats": {},
            }

    class FakeDb:
        def __getitem__(self, _collection):
            return FakeCollection()

    persisted = {}
    service = sync_source.MultiSourceBasicsSyncService()

    async def fake_persist(_db, stats):
        persisted.update(stats)
        service._last_status = dict(stats)

    monkeypatch.setattr(sync_source, "get_postgres_db", lambda: FakeDb())
    monkeypatch.setattr(service, "_persist_status", fake_persist)

    status = await service.get_status()

    assert status["status"] == "failed"
    assert status["message"] == "上次同步任务异常中断，请重新启动同步"
    assert status["finished_at"] is not None
    assert persisted["status"] == "failed"
