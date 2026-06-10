from __future__ import annotations

import pytest

from app.routers import analysis as admin_module


class _MemoryManager:
    async def remove_task(self, task_id: str):
        self.removed_task_id = task_id


class _Service:
    def __init__(self) -> None:
        self.memory_manager = _MemoryManager()


class _DeleteResult:
    deleted_count = 0


class _AnalysisTasks:
    async def delete_one(self, query: dict):
        self.deleted_query = query
        return _DeleteResult()


class _Db:
    def __init__(self) -> None:
        self.analysis_tasks = _AnalysisTasks()


@pytest.mark.asyncio
async def test_delete_task_reports_success_when_structured_row_deleted(monkeypatch):
    monkeypatch.setattr(admin_module, "get_simple_analysis_service", lambda: _Service())
    monkeypatch.setattr(admin_module, "get_postgres_db", lambda: _Db())

    async def fake_delete_structured_rows(task_id: str):
        return 1

    monkeypatch.setattr(
        admin_module,
        "_delete_analysis_task_structured_rows",
        fake_delete_structured_rows,
        raising=False,
    )

    result = await admin_module.delete_task("task-1", {"id": "u1"})

    assert result == {"success": True, "message": "任务已删除"}
