from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers.research import agent as research_agent_router
from app.services.research.agent import events as events_module
from app.services.research.agent import goals as goals_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.events import ResearchEventService
from app.services.research.agent.goals import ResearchGoalConflictError, ResearchGoalService
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.sessions import ResearchSessionService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if document.get(key) != expected:
            return False
    return True


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
        return type("FakeInsertResult", (), {"inserted_id": document.get("_id")})()

    async def find_one(self, query: dict[str, Any], *_args: Any, **kwargs: Any):
        rows = [doc for doc in self.documents if _matches_query(doc, query)]
        if sort := kwargs.get("sort"):
            key, direction = sort[0]
            rows = sorted(rows, key=lambda item: item.get(key, 0), reverse=direction < 0)
        return dict(rows[0]) if rows else None

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

    async def delete_many(self, query: dict[str, Any]):
        before = len(self.documents)
        self.documents = [
            document for document in self.documents if not _matches_query(document, query)
        ]
        return type("FakeDeleteResult", (), {"deleted_count": before - len(self.documents)})()


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()
        self.research_jobs = FakeCollection()
        self.research_attempts = FakeCollection()
        self.research_goals = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, goals_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any]) -> ResearchPrincipal:
    return ResearchPrincipal.from_user(user, session_id="session-a")


@pytest.mark.asyncio
async def test_goal_service_owner_scope_stale_update_and_evidence(fake_db):
    _ = fake_db
    service = ResearchGoalService()
    goal = await service.create_goal(
        principal=_principal(USER_A),
        session_id="session-a",
        title="验证储能研究",
        description="完成证据链",
        criteria=["有工具证据"],
    )

    assert await service.get_goal("session-a", USER_B["id"]) is None
    with pytest.raises(ResearchGoalConflictError):
        await service.update_goal(
            session_id="session-a",
            user_id=USER_A["id"],
            expected_goal_id="stale",
            updates={"title": "错误更新"},
        )

    updated = await service.add_evidence(
        session_id="session-a",
        user_id=USER_A["id"],
        expected_goal_id=goal["goal_id"],
        evidence={"kind": "tool", "summary": "alpha bench completed"},
    )
    completed = await service.update_status(
        session_id="session-a",
        user_id=USER_A["id"],
        expected_goal_id=goal["goal_id"],
        status="complete",
        reason="证据充分",
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]

    assert updated["evidence"][0]["summary"] == "alpha bench completed"
    assert completed["status"] == "complete"
    assert event_types == ["goal.created", "goal.evidence", "goal.updated"]


@pytest.mark.asyncio
async def test_goal_routes_enforce_session_owner_and_stale_update(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.goal_service = ResearchGoalService(
        event_service=research_agent_router.event_service
    )

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="目标会话"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]
    goal_response = await research_agent_router.create_research_goal(
        session_id,
        research_agent_router.ResearchGoalCreateRequest(title="目标", criteria=["完成"]),
        current_user=USER_A,
    )

    with pytest.raises(HTTPException) as owner_exc:
        await research_agent_router.get_research_goal(session_id, current_user=USER_B)
    with pytest.raises(HTTPException) as stale_exc:
        await research_agent_router.update_research_goal(
            session_id,
            research_agent_router.ResearchGoalUpdateRequest(
                expected_goal_id="stale", title="旧目标"
            ),
            current_user=USER_A,
        )

    assert goal_response["data"]["goal_id"]
    assert owner_exc.value.status_code == 404
    assert stale_exc.value.status_code == 409


@pytest.mark.asyncio
async def test_goal_tools_are_real_current_project_tools(fake_db):
    _ = fake_db
    session = await ResearchSessionService().create_session(
        _principal(USER_A), title="目标工具"
    )
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session["session_id"]),
        session_id=session["session_id"],
    )

    goal = await registry.get("start_research_goal").run(
        context, {"title": "工具目标", "criteria": ["有证据"]}
    )
    fetched = await registry.get("get_research_goal").run(context, {})

    assert goal["title"] == "工具目标"
    assert fetched["goal_id"] == goal["goal_id"]


@pytest.mark.asyncio
async def test_goal_evidence_tool_rejects_stale_goal_id_without_writing(fake_db):
    _ = fake_db
    session = await ResearchSessionService().create_session(
        _principal(USER_A), title="目标工具"
    )
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session["session_id"]),
        session_id=session["session_id"],
    )
    goal = await registry.get("start_research_goal").run(
        context, {"title": "工具目标", "criteria": ["有证据"]}
    )

    result = await registry.get("add_goal_evidence").run(
        context,
        {
            "expected_goal_id": "stale-goal-id",
            "evidence": {"kind": "tool", "summary": "多因子回测数据源受限"},
        },
    )
    current = await registry.get("get_research_goal").run(context, {})

    assert result["status"] == "stale_goal"
    assert result["accepted"] is False
    assert result["written"] is False
    assert result["current_goal_id"] == goal["goal_id"]
    assert current["evidence"] == []
