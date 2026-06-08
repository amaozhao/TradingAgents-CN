from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import research_matrix as research_matrix_router
from app.services.research_agent import artifacts as artifacts_module
from app.services.research_agent import events as events_module
from app.services.research_agent import jobs as jobs_module
from app.services.research_agent.tools.correlation import ResearchMatrixJobService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not actual > expected["$gt"]:
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeInsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.documents = sorted(
            self.documents, key=lambda item: item.get(key, 0), reverse=reverse
        )
        return self

    def __aiter__(self):
        self._iter = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self):
        self.documents: list[dict[str, Any]] = []

    async def insert_one(self, document: dict[str, Any]):
        self.documents.append(dict(document))
        return FakeInsertResult(str(document.get("_id")))

    async def find_one(self, query: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                return dict(document)
        return None

    def find(self, query: dict[str, Any]):
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                document.update(update.get("$set", {}))
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    async def count_documents(self, query: dict[str, Any]):
        return len([doc for doc in self.documents if _matches_query(doc, query)])


class FakeDb:
    def __init__(self):
        self.research_jobs = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (jobs_module, events_module, artifacts_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    research_matrix_router.matrix_job_service = ResearchMatrixJobService()
    return db


@pytest.mark.asyncio
async def test_user_can_create_matrix_job_from_explicit_symbols(fake_db):
    response = await research_matrix_router.create_correlation_matrix_job(
        research_matrix_router.CorrelationMatrixRequest(
            symbols=["600519", "000001", "300750"],
            method="pearson",
            window=20,
        ),
        current_user=USER_A,
    )

    job = response["data"]
    assert job["user_id"] == USER_A["id"]
    assert job["status"] == "completed"
    assert job["result"]["artifact_id"]
    assert job["result"]["matrix"]
    assert fake_db.research_artifacts.documents[0]["user_id"] == USER_A["id"]


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_matrix_job(fake_db):
    created = await research_matrix_router.create_correlation_matrix_job(
        research_matrix_router.CorrelationMatrixRequest(symbols=["600519", "000001"]),
        current_user=USER_A,
    )

    with pytest.raises(HTTPException) as exc:
        await research_matrix_router.get_matrix_job(
            created["data"]["job_id"], current_user=USER_B
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_matrix_events(fake_db):
    created = await research_matrix_router.create_correlation_matrix_job(
        research_matrix_router.CorrelationMatrixRequest(symbols=["600519", "000001"]),
        current_user=USER_A,
    )

    with pytest.raises(HTTPException) as exc:
        await research_matrix_router.list_matrix_job_events(
            created["data"]["job_id"], current_user=USER_B
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_or_unowned_screening_result_id_returns_404(fake_db):
    _ = fake_db

    with pytest.raises(HTTPException) as exc:
        await research_matrix_router.create_correlation_matrix_job(
            research_matrix_router.CorrelationMatrixRequest(
                screening_result_id="screening-private-b",
            ),
            current_user=USER_A,
        )

    assert exc.value.status_code == 404
