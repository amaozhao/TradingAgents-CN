from __future__ import annotations

import pytest

from app.schemas.analysis import AnalysisStatus
from app.services.analysis.simple import status as status_module
from app.services.analysis.simple.status import AnalysisStatusMixin


class _FakeAnalysisTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict]] = []

    async def update_one(self, query: dict, update: dict):
        self.calls.append((query, update))


class _FakeDb:
    def __init__(self) -> None:
        self.analysis_tasks = _FakeAnalysisTasks()


@pytest.mark.asyncio
async def test_completed_status_writes_final_step_and_message(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(status_module, "get_postgres_db", lambda: db)

    await AnalysisStatusMixin()._update_task_status(
        "task-1", AnalysisStatus.COMPLETED, 100
    )

    query, update = db.analysis_tasks.calls[0]
    assert query == {"task_id": "task-1"}
    assert update["$set"]["status"] == AnalysisStatus.COMPLETED
    assert update["$set"]["progress"] == 100
    assert update["$set"]["current_step"] == "completed"
    assert update["$set"]["message"] == "分析完成"
    assert "completed_at" in update["$set"]


@pytest.mark.asyncio
async def test_failed_status_writes_error_step_and_message(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(status_module, "get_postgres_db", lambda: db)

    await AnalysisStatusMixin()._update_task_status(
        "task-2", AnalysisStatus.FAILED, 90, "LLM请求超时"
    )

    _, update = db.analysis_tasks.calls[0]
    assert update["$set"]["status"] == AnalysisStatus.FAILED
    assert update["$set"]["current_step"] == "failed"
    assert update["$set"]["message"] == "LLM请求超时"
    assert update["$set"]["last_error"] == "LLM请求超时"
