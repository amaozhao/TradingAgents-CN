import pytest

from app.services.analysis.simple import SimpleAnalysisService


@pytest.mark.asyncio
async def test_list_user_tasks_uses_postgres_history_when_available(monkeypatch):
    service = SimpleAnalysisService.__new__(SimpleAnalysisService)
    service.memory_manager = FakeMemoryManager()
    service._progress_trackers = {}
    service._enrich_stock_names = lambda tasks: tasks

    async def fake_pg_history(**kwargs):
        assert kwargs["user_id"] == "user-1"
        assert kwargs["status"] == "completed"
        return [
            {
                "task_id": "task-1",
                "user_id": "user-1",
                "symbol": "000001",
                "stock_code": "000001",
                "stock_symbol": "000001",
                "status": "completed",
                "progress": 100,
                "start_time": "2026-06-03T10:00:00+08:00",
            }
        ]

    async def fail_mongo_history(**_kwargs):
        raise AssertionError("Mongo fallback should not be used when PostgreSQL returns history")

    monkeypatch.setattr(service, "_list_user_tasks_from_postgres", fake_pg_history)
    monkeypatch.setattr(service, "_list_user_tasks_from_mongo", fail_mongo_history)

    tasks = await service.list_user_tasks("user-1", status="completed", limit=20, offset=0)

    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "task-1"
    assert tasks[0]["stock_code"] == "000001"


class FakeMemoryManager:
    async def list_user_tasks(self, **_kwargs):
        return []
