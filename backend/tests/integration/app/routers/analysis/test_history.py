from __future__ import annotations

import pytest

from app.services.analysis.simple import SimpleAnalysisService


class FakeMemoryManager:
    async def list_user_tasks(self, **_kwargs):
        return [
            {
                "task_id": "task-1",
                "user_id": "user-1",
                "stock_code": "601989",
                "stock_symbol": "601989",
                "stock_name": "中国重工",
                "status": "pending",
                "progress": 0,
                "message": "任务已创建，等待执行...",
                "start_time": "2026-06-11T17:23:34+08:00",
            }
        ]


class EmptyMemoryManager:
    async def list_user_tasks(self, **_kwargs):
        return []


@pytest.mark.asyncio
async def test_list_user_tasks_prefers_terminal_postgres_status_over_stale_memory(
    monkeypatch,
):
    service = SimpleAnalysisService.__new__(SimpleAnalysisService)
    service.memory_manager = FakeMemoryManager()
    service._enrich_stock_names = lambda tasks: tasks

    async def postgres_table_tasks(**kwargs):
        assert kwargs["user_id"] == "user-1"
        return [
            {
                "task_id": "task-1",
                "user_id": "user-1",
                "stock_code": "601989",
                "stock_symbol": "601989",
                "stock_name": "中国重工",
                "status": "failed",
                "progress": 0,
                "message": "无法获取股票 601989 的历史数据",
                "last_error": "无法获取股票 601989 的历史数据",
                "start_time": "2026-06-11T17:23:34+08:00",
                "end_time": "2026-06-11T17:28:31+08:00",
            }
        ]

    monkeypatch.setattr(
        service, "_list_user_tasks_from_postgres_tables", postgres_table_tasks
    )

    async def postgres_document_tasks(**_kwargs):
        raise AssertionError("document fallback should not run when table tasks exist")

    monkeypatch.setattr(
        service, "_list_user_tasks_from_postgres_documents", postgres_document_tasks
    )

    tasks = await service.list_user_tasks("user-1", limit=20, offset=0)

    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "task-1"
    assert tasks[0]["status"] == "failed"
    assert tasks[0]["message"] == "无法获取股票 601989 的历史数据"


@pytest.mark.asyncio
async def test_list_user_tasks_filters_batch_id_after_owner_scoped_lookup(monkeypatch):
    service = SimpleAnalysisService.__new__(SimpleAnalysisService)
    service.memory_manager = EmptyMemoryManager()
    service._enrich_stock_names = lambda tasks: tasks

    async def postgres_table_tasks(**kwargs):
        assert kwargs["user_id"] == "user-1"
        assert kwargs["batch_id"] == "batch-1"
        return [
            {
                "task_id": "task-1",
                "user_id": "user-1",
                "batch_id": "batch-1",
                "stock_code": "600036",
                "status": "completed",
                "progress": 100,
                "start_time": "2026-06-12T10:00:00+08:00",
            },
            {
                "task_id": "task-2",
                "user_id": "user-1",
                "batch_id": "batch-2",
                "stock_code": "000001",
                "status": "completed",
                "progress": 100,
                "start_time": "2026-06-12T10:01:00+08:00",
            },
        ]

    monkeypatch.setattr(
        service, "_list_user_tasks_from_postgres_tables", postgres_table_tasks
    )

    async def postgres_document_tasks(**_kwargs):
        raise AssertionError("document fallback should not run when table tasks exist")

    monkeypatch.setattr(
        service, "_list_user_tasks_from_postgres_documents", postgres_document_tasks
    )

    tasks = await service.list_user_tasks(
        "user-1",
        limit=20,
        offset=0,
        batch_id="batch-1",
    )

    assert [task["task_id"] for task in tasks] == ["task-1"]
    assert tasks[0]["batch_id"] == "batch-1"


@pytest.mark.asyncio
async def test_list_user_tasks_dependency_failure_is_not_silent_empty_success(
    monkeypatch,
):
    class FailingMemoryManager:
        async def list_user_tasks(self, **_kwargs):
            raise RuntimeError("memory unavailable")

    service = SimpleAnalysisService.__new__(SimpleAnalysisService)
    service.memory_manager = FailingMemoryManager()
    service._enrich_stock_names = lambda tasks: tasks

    async def postgres_table_tasks(**_kwargs):
        raise RuntimeError("postgres unavailable")

    monkeypatch.setattr(
        service, "_list_user_tasks_from_postgres_tables", postgres_table_tasks
    )

    tasks = await service.list_user_tasks("user-1", limit=20, offset=0)

    assert tasks != []
    assert tasks[0]["degraded"] is True
    assert tasks[0]["warnings"] == [
        "memory_task_status_unavailable",
        "postgres_task_status_unavailable",
    ]
