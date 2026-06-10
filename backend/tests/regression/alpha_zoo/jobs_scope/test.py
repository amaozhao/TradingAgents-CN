from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import alpha_zoo as alpha_zoo_router
from app.services.alpha_zoo.jobs import AlphaZooJobService
from app.services.research_agent import artifacts as artifacts_module
from app.services.research_agent import events as events_module
from app.services.research_agent import jobs as jobs_module


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
    alpha_zoo_router.alpha_job_service = AlphaZooJobService()
    return db


@pytest.mark.asyncio
async def test_factor_list_is_available_to_authenticated_users(fake_db):
    _ = fake_db

    response_a = await alpha_zoo_router.list_alpha_factors(current_user=USER_A)
    response_b = await alpha_zoo_router.list_alpha_factors(current_user=USER_B)

    assert response_a["success"] is True
    assert response_b["success"] is True
    assert response_a["data"]["total"] == response_b["data"]["total"]
    factor_ids = [item["factor_id"] for item in response_a["data"]["items"]]
    assert any(factor_id.startswith("alpha") for factor_id in factor_ids)


@pytest.mark.asyncio
async def test_user_can_create_own_bench_job_and_artifact(fake_db):
    response = await alpha_zoo_router.create_alpha_bench_job(
        alpha_zoo_router.AlphaBenchRequest(
            alpha_id="alpha101_001",
            symbols=["600519", "000001"],
            start_date="2026-06-01",
            end_date="2026-06-03",
        ),
        current_user=USER_A,
    )

    job = response["data"]
    assert job["user_id"] == USER_A["id"]
    assert job["status"] == "completed"
    assert job["result"]["artifact_id"]
    assert fake_db.research_artifacts.documents[0]["user_id"] == USER_A["id"]


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_bench_job(fake_db):
    created = await alpha_zoo_router.create_alpha_bench_job(
        alpha_zoo_router.AlphaBenchRequest(alpha_id="alpha101_001", symbols=["600519"]),
        current_user=USER_A,
    )

    with pytest.raises(HTTPException) as exc:
        await alpha_zoo_router.get_alpha_job(
            created["data"]["job_id"], current_user=USER_B
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_read_other_users_bench_events(fake_db):
    created = await alpha_zoo_router.create_alpha_bench_job(
        alpha_zoo_router.AlphaBenchRequest(alpha_id="alpha101_001", symbols=["600519"]),
        current_user=USER_A,
    )

    with pytest.raises(HTTPException) as exc:
        await alpha_zoo_router.list_alpha_job_events(
            created["data"]["job_id"], current_user=USER_B
        )

    assert exc.value.status_code == 404
