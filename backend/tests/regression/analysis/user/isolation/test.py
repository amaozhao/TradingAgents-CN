from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import analysis


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _get_nested(document: dict[str, Any], key: str) -> Any:
    current: Any = document
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    if not query:
        return True
    if "$and" in query:
        return all(_matches_query(document, item) for item in query["$and"])
    if "$or" in query:
        return any(_matches_query(document, item) for item in query["$or"])

    for key, expected in query.items():
        actual = _get_nested(document, key)
        if isinstance(expected, dict):
            if "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue
            raise AssertionError(f"unsupported fake query operator: {expected}")
        if actual != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None):
        self.documents = documents or []
        self.last_find_one_query: dict[str, Any] | None = None

    async def find_one(self, query: dict[str, Any], *_args):
        self.last_find_one_query = query
        for document in self.documents:
            if _matches_query(document, query):
                return document
        return None


class FakeDb:
    def __init__(
        self,
        *,
        tasks: list[dict[str, Any]] | None = None,
        reports: list[dict[str, Any]] | None = None,
    ):
        self.analysis_tasks = FakeCollection(tasks)
        self.analysis_reports = FakeCollection(reports)


class FakeAnalysisService:
    def __init__(self, task_status: dict[str, Any] | None = None):
        self.task_status = task_status
        self.calls: list[tuple[str, str | None]] = []

    async def get_task_status(self, task_id: str, user_id: str | None = None):
        self.calls.append((task_id, user_id))
        if not self.task_status:
            return None
        owner = self.task_status.get("user_id") or self.task_status.get("user")
        if user_id is not None and str(owner) != str(user_id):
            return None
        return self.task_status


def _task_document(user_id: str) -> dict[str, Any]:
    return {
        "task_id": "task-b",
        "user_id": user_id,
        "symbol": "600519",
        "status": "running",
        "progress": 35,
        "message": "处理中",
        "current_step": "news",
        "created_at": datetime(2026, 6, 8),
        "started_at": datetime(2026, 6, 8),
    }


def _report_document(user_id: str) -> dict[str, Any]:
    return {
        "analysis_id": "analysis-b",
        "task_id": "task-b",
        "user_id": user_id,
        "stock_symbol": "600519",
        "analysis_date": "2026-06-08",
        "summary": "private summary",
        "recommendation": "private recommendation",
        "reports": {"summary": "private report"},
        "status": "completed",
        "created_at": datetime(2026, 6, 8),
        "updated_at": datetime(2026, 6, 8),
    }


@pytest.fixture(autouse=True)
def disable_structured_postgres(monkeypatch):
    monkeypatch.setattr(analysis.settings, "POSTGRES_READ_ENABLED", False)


@pytest.mark.asyncio
async def test_status_rejects_other_users_in_memory_task(monkeypatch):
    service = FakeAnalysisService(
        {
            "task_id": "task-b",
            "user_id": USER_B["id"],
            "status": "running",
            "progress": 10,
            "message": "private",
        }
    )
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr(
        "app.core.database.get_postgres_db", lambda: FakeDb(tasks=[], reports=[])
    )

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_status_new("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert service.calls == [("task-b", USER_A["id"])]


@pytest.mark.asyncio
async def test_status_task_fallback_rejects_other_users_task(monkeypatch):
    service = FakeAnalysisService()
    db = FakeDb(tasks=[_task_document(USER_B["id"])], reports=[])
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr("app.core.database.get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_status_new("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert db.analysis_tasks.last_find_one_query is not None
    assert "$and" in db.analysis_tasks.last_find_one_query


@pytest.mark.asyncio
async def test_status_report_fallback_rejects_other_users_report(monkeypatch):
    service = FakeAnalysisService()
    db = FakeDb(tasks=[], reports=[_report_document(USER_B["id"])])
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr("app.core.database.get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_status_new("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert db.analysis_reports.last_find_one_query is not None
    assert "$and" in db.analysis_reports.last_find_one_query


@pytest.mark.asyncio
async def test_result_rejects_other_users_in_memory_task(monkeypatch):
    service = FakeAnalysisService(
        {
            "task_id": "task-b",
            "user_id": USER_B["id"],
            "status": "completed",
            "result_data": _report_document(USER_B["id"]),
        }
    )
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr(
        "app.core.database.get_postgres_db", lambda: FakeDb(tasks=[], reports=[])
    )

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_result("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert service.calls == [("task-b", USER_A["id"])]


@pytest.mark.asyncio
async def test_result_report_fallback_rejects_other_users_report(monkeypatch):
    service = FakeAnalysisService()
    db = FakeDb(tasks=[], reports=[_report_document(USER_B["id"])])
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr("app.core.database.get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_result("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert db.analysis_reports.last_find_one_query is not None
    assert "$and" in db.analysis_reports.last_find_one_query


@pytest.mark.asyncio
async def test_result_task_result_fallback_rejects_other_users_task(monkeypatch):
    service = FakeAnalysisService()
    task = _task_document(USER_B["id"])
    task["status"] = "completed"
    task["result"] = _report_document(USER_B["id"])
    db = FakeDb(tasks=[task], reports=[])
    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr("app.core.database.get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await analysis.get_task_result("task-b", user=USER_A)

    assert exc.value.status_code == 404
    assert db.analysis_tasks.last_find_one_query is not None
    assert "$and" in db.analysis_tasks.last_find_one_query
