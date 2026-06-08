from __future__ import annotations

from typing import Any

import pytest

from app.services.research_agent import events as events_module
from app.services.research_agent import jobs as jobs_module
from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.jobs import ResearchJobService


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


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(jobs_module, "get_postgres_db", lambda: db)
    monkeypatch.setattr(events_module, "get_postgres_db", lambda: db)
    return db


def _principal(user: dict[str, Any]) -> ResearchPrincipal:
    return ResearchPrincipal.from_user(user)


@pytest.mark.asyncio
async def test_enqueue_supports_non_symbol_jobs_and_owner_status(fake_db):
    service = ResearchJobService()

    job = await service.enqueue(
        principal=_principal(USER_A),
        task_type="correlation",
        resource_id="artifact-1",
        payload={"symbols": ["300750.SZ", "002594.SZ"]},
    )

    assert job["symbol"] is None
    assert job["user_id"] == USER_A["id"]
    assert job["status"] == "queued"
    assert await service.get(job["job_id"], USER_A["id"]) is not None
    assert await service.get(job["job_id"], USER_B["id"]) is None


@pytest.mark.asyncio
async def test_cancel_and_job_events_are_owner_scoped(fake_db):
    service = ResearchJobService()
    job = await service.enqueue(
        principal=_principal(USER_A),
        task_type="correlation",
        resource_id="artifact-1",
        payload={"symbols": ["300750.SZ", "002594.SZ"]},
    )

    assert await service.cancel(job["job_id"], USER_B["id"]) is False
    assert await service.cancel(job["job_id"], USER_A["id"]) is True
    cancelled = await service.get(job["job_id"], USER_A["id"])
    events = await service.list_events(job["job_id"], USER_A["id"], after_event_id=0)
    other_events = await service.list_events(job["job_id"], USER_B["id"])

    assert cancelled["status"] == "cancelled"
    assert [event["event_type"] for event in events] == ["job_queued", "job_cancelled"]
    assert other_events == []


@pytest.mark.asyncio
async def test_job_state_transitions_persist_events(fake_db):
    service = ResearchJobService()
    job = await service.enqueue(
        principal=_principal(USER_A),
        task_type="alpha_bench",
        resource_id="alpha-1",
        payload={"alpha_id": "alpha-1"},
        symbol="600519",
    )

    await service.mark_running(job["job_id"])
    await service.mark_completed(job["job_id"], {"score": 0.7})
    completed = await service.get(job["job_id"], USER_A["id"])
    events = await service.list_events(job["job_id"], USER_A["id"], after_event_id=1)

    assert completed["status"] == "completed"
    assert completed["result"] == {"score": 0.7}
    assert [event["event_type"] for event in events] == [
        "job_running",
        "job_completed",
    ]
