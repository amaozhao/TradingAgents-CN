from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import reports as reports_router
from app.services.analysis.simple import reports as report_service_module
from app.services.analysis.simple.reports import AnalysisReportMixin


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    if not query:
        return True
    if "$and" in query:
        return all(_matches_query(document, item) for item in query["$and"])
    if "$or" in query:
        return any(_matches_query(document, item) for item in query["$or"])
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$regex" in expected:
                if str(expected["$regex"]).lower() not in str(actual or "").lower():
                    return False
                continue
            if "$gte" in expected and actual < expected["$gte"]:
                return False
            if "$lte" in expected and actual > expected["$lte"]:
                return False
        elif actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self._documents = documents

    def sort(self, *_args):
        return self

    async def to_list(self, _length):
        return self._documents


class FakeDeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class FakeInsertResult:
    inserted_id = "inserted-report-id"


class FakeReportCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None):
        self.documents = documents or []
        self.inserted: list[dict[str, Any]] = []
        self.last_find_query: dict[str, Any] | None = None
        self.last_find_one_query: dict[str, Any] | None = None
        self.last_delete_query: dict[str, Any] | None = None

    def find(self, query: dict[str, Any]):
        self.last_find_query = query
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def find_one(self, query: dict[str, Any], *_args):
        self.last_find_one_query = query
        for doc in self.documents:
            if _matches_query(doc, query):
                return doc
        return None

    async def insert_one(self, document: dict[str, Any]):
        self.inserted.append(document)
        self.documents.append(document)
        return FakeInsertResult()

    async def delete_one(self, query: dict[str, Any]):
        self.last_delete_query = query
        before = len(self.documents)
        self.documents = [
            doc for doc in self.documents if not _matches_query(doc, query)
        ]
        return FakeDeleteResult(before - len(self.documents))


class FakeTaskCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None):
        self.documents = documents or []
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.last_find_one_query: dict[str, Any] | None = None

    async def find_one(self, query: dict[str, Any], *_args):
        self.last_find_one_query = query
        for doc in self.documents:
            if _matches_query(doc, query):
                return doc
        return None

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        self.updates.append((query, update))


class FakeReportDb:
    def __init__(
        self,
        reports: list[dict[str, Any]] | None = None,
        tasks: list[dict[str, Any]] | None = None,
    ):
        self.analysis_reports = FakeReportCollection(reports)
        self.analysis_tasks = FakeTaskCollection(tasks)


def _report(report_id: str, user_id: str, stock_symbol: str) -> dict[str, Any]:
    return {
        "_id": report_id,
        "analysis_id": f"analysis-{report_id}",
        "task_id": f"task-{report_id}",
        "user_id": user_id,
        "stock_symbol": stock_symbol,
        "stock_name": stock_symbol,
        "summary": f"{stock_symbol} report",
        "reports": {"summary": f"{stock_symbol} content"},
        "created_at": "2026-06-08T00:00:00",
        "updated_at": "2026-06-08T00:00:00",
        "analysis_date": "2026-06-08",
    }


@pytest.mark.asyncio
async def test_report_list_returns_only_current_user_reports(monkeypatch):
    captured: dict[str, Any] = {}
    requested_names: list[str] = []

    class FakeSession:
        pass

    class FakeSessionFactory:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *_args):
            return None

    async def fake_list_user_analysis_reports(_session, **kwargs):
        captured.update(kwargs)
        return (
            [
                {
                    "id": "report-a",
                    "analysis_id": "analysis-report-a",
                    "task_id": "task-report-a",
                    "user_id": USER_A["id"],
                    "stock_symbol": "300750.SZ",
                    "stock_name": "300750.SZ",
                    "summary": "300750.SZ report",
                    "created_at": "2026-06-08T00:00:00",
                    "analysis_date": "2026-06-08",
                }
            ],
            1,
        )

    monkeypatch.setattr(
        reports_router, "get_session_factory", lambda: FakeSessionFactory
    )
    monkeypatch.setattr(
        reports_router, "list_user_analysis_reports", fake_list_user_analysis_reports
    )

    async def fake_get_stock_names(codes: list[str]):
        requested_names.extend(codes)
        return {code: code for code in codes}

    monkeypatch.setattr(reports_router, "get_stock_names", fake_get_stock_names)

    response = await reports_router.get_reports_list(
        page=1,
        page_size=20,
        search_keyword=None,
        keyword=None,
        market_filter=None,
        market=None,
        start_date=None,
        end_date=None,
        stock_code=None,
        user=USER_A,
    )

    assert response["success"] is True
    assert response["data"]["reports"][0]["id"] == "analysis-report-a"
    ids = {item["analysis_id"] for item in response["data"]["reports"]}
    assert ids == {"analysis-report-a"}
    assert captured["user_id"] == USER_A["id"]
    assert captured["is_admin"] is False
    assert captured["limit"] == 20
    assert captured["offset"] == 0
    assert requested_names == ["300750.SZ"]


@pytest.mark.asyncio
async def test_report_detail_rejects_other_users_report(monkeypatch):
    db = FakeReportDb([_report("report-b", USER_B["id"], "002594.SZ")])
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await reports_router.get_report_detail("analysis-report-b", user=USER_A)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_detail_task_fallback_rejects_other_users_task(monkeypatch):
    db = FakeReportDb(
        tasks=[
            {
                "task_id": "task-b",
                "user_id": USER_B["id"],
                "stock_code": "002594.SZ",
                "created_at": datetime(2026, 6, 8),
                "completed_at": datetime(2026, 6, 8),
                "result": {
                    "analysis_id": "analysis-b",
                    "stock_symbol": "002594.SZ",
                    "reports": {"summary": "private"},
                },
            }
        ]
    )
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await reports_router.get_report_detail("task-b", user=USER_A)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_module_content_rejects_other_users_report(monkeypatch):
    db = FakeReportDb([_report("report-b", USER_B["id"], "002594.SZ")])
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await reports_router.get_report_module_content(
            "analysis-report-b", "summary", user=USER_A
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_download_rejects_other_users_report(monkeypatch):
    db = FakeReportDb([_report("report-b", USER_B["id"], "002594.SZ")])
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await reports_router.download_report(
            "analysis-report-b", format="json", user=USER_A
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_report_delete_rejects_other_users_report(monkeypatch):
    db = FakeReportDb([_report("report-b", USER_B["id"], "002594.SZ")])
    monkeypatch.setattr(reports_router, "get_postgres_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await reports_router.delete_report("analysis-report-b", user=USER_A)

    assert exc.value.status_code == 404
    assert len(db.analysis_reports.documents) == 1


@pytest.mark.asyncio
async def test_web_style_report_save_persists_task_owner(monkeypatch):
    db = FakeReportDb(
        tasks=[
            {
                "task_id": "task-a",
                "user_id": USER_A["id"],
            }
        ]
    )
    monkeypatch.setattr(report_service_module, "get_postgres_db", lambda: db)
    monkeypatch.setattr(
        report_service_module, "dual_write_hot_document", _noop_dual_write
    )

    await AnalysisReportMixin()._save_analysis_result_web_style(
        "task-a",
        {
            "stock_symbol": "AAPL",
            "summary": "summary",
            "reports": {"summary": "content"},
        },
    )

    assert db.analysis_reports.inserted
    assert db.analysis_reports.inserted[0]["user_id"] == USER_A["id"]


async def _noop_dual_write(*_args, **_kwargs):
    return None
