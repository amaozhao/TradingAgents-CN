from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import research_agent as research_agent_router
from app.services.research_agent import artifacts as artifacts_module
from app.services.research_agent import events as events_module
from app.services.research_agent import jobs as jobs_module
from app.services.research_agent import sessions as sessions_module
from app.services.research_agent.artifacts import ResearchArtifactService
from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.events import ResearchEventService
from app.services.research_agent.sessions import ResearchSessionService


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


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.documents = sorted(
            self.documents, key=lambda item: item.get(key, 0), reverse=reverse
        )
        return self

    def limit(self, limit: int):
        self.documents = self.documents[:limit]
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

    async def count_documents(self, query: dict[str, Any]):
        return len([doc for doc in self.documents if _matches_query(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                document.update(update.get("$set", {}))
                return type("FakeUpdateResult", (), {"modified_count": 1})()
        return type("FakeUpdateResult", (), {"modified_count": 0})()


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()
        self.research_jobs = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, artifacts_module, jobs_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any]) -> ResearchPrincipal:
    return ResearchPrincipal.from_user(user, session_id="request-session")


@pytest.mark.asyncio
async def test_user_can_create_and_list_only_own_sessions(fake_db):
    service = ResearchSessionService()
    session_a = await service.create_session(_principal(USER_A), title="储能分析")
    await service.create_session(_principal(USER_B), title="白酒分析")

    listed = await service.list_sessions(user_id=USER_A["id"])

    assert session_a["session_id"]
    assert [item["session_id"] for item in listed] == [session_a["session_id"]]
    assert await service.get_session(session_a["session_id"], USER_A["id"]) is not None
    assert await service.get_session(session_a["session_id"], USER_B["id"]) is None


@pytest.mark.asyncio
async def test_messages_and_events_replay_are_owner_scoped(fake_db):
    session_service = ResearchSessionService()
    event_service = ResearchEventService()
    principal = _principal(USER_A)
    session = await session_service.create_session(principal, title="储能分析")
    session_id = session["session_id"]

    message = await session_service.append_message(
        session_id=session_id,
        user_id=USER_A["id"],
        role="user",
        content="分析储能产业链",
    )
    first = await event_service.append(
        session_id=session_id,
        user_id=USER_A["id"],
        event_type="message",
        payload={"message_id": message["message_id"]},
    )
    second = await event_service.append(
        session_id=session_id,
        user_id=USER_A["id"],
        event_type="tool",
        payload={"tool": "market_data_lookup"},
    )

    messages = await session_service.list_messages(session_id, USER_A["id"])
    replay = await event_service.list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=first["event_id"]
    )
    other_user_replay = await event_service.list_after(
        session_id=session_id, user_id=USER_B["id"], after_event_id=0
    )

    assert messages[0]["content"] == "分析储能产业链"
    assert [event["event_id"] for event in replay] == [second["event_id"]]
    assert other_user_replay == []


@pytest.mark.asyncio
async def test_artifact_lookup_enforces_owner(fake_db):
    session = await ResearchSessionService().create_session(
        _principal(USER_A), title="储能分析"
    )
    artifact_service = ResearchArtifactService()
    artifact = await artifact_service.create_artifact(
        session_id=session["session_id"],
        user_id=USER_A["id"],
        artifact_type="report",
        payload={"summary": "private"},
    )

    assert await artifact_service.get_artifact(artifact["artifact_id"], USER_A["id"])
    assert await artifact_service.get_artifact(artifact["artifact_id"], USER_B["id"]) is None


@pytest.mark.asyncio
async def test_research_agent_routes_enforce_session_ownership(fake_db):
    monkeypatch_service = ResearchSessionService()
    research_agent_router.session_service = monkeypatch_service
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="储能分析"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    with pytest.raises(HTTPException) as exc:
        await research_agent_router.get_research_session(session_id, current_user=USER_B)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_user_prompt_route_runs_agent_workflow_and_persists_artifacts(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="储能分析"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    response = await research_agent_router.append_research_message(
        session_id,
        research_agent_router.ResearchMessageCreateRequest(
            role="user", content="分析 A 股储能板块，给出推荐个股"
        ),
        current_user=USER_A,
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    event_types = [event["event_type"] for event in events]
    artifacts = fake_db.research_artifacts.documents

    assert response["success"] is True
    assert response["data"]["status"] == "completed"
    assert response["data"]["artifact_ids"]
    assert "tool_completed" in event_types
    assert "message_completed" in event_types
    assert "task_completed" in event_types
    assert any(artifact["artifact_type"] == "research_report" for artifact in artifacts)
