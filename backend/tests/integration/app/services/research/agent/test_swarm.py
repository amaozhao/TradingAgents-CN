from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers.research import agent as research_agent_router
from app.services.research.agent import events as events_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent import swarm as swarm_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.events import ResearchEventService
from app.services.research.agent.loop import ModelStreamChunk
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.sessions import ResearchSessionService
from app.services.research.agent.swarm import DEFAULT_SWARM_PRESETS, ResearchSwarmService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not (value is not None and value > expected["$gt"]):
                return False
            continue
        if value != expected:
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
        self.research_swarm_runs = FakeCollection()
        self.research_swarm_events = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, swarm_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any], session_id: str | None = "session-a") -> ResearchPrincipal:
    return ResearchPrincipal.from_user(user, session_id=session_id)


class FakeWorkerModelClient:
    def __init__(self, _principal: ResearchPrincipal):
        pass

    async def stream(self, **_kwargs: Any):
        yield ModelStreamChunk(delta="worker summary", finish_reason="stop")


@pytest.mark.asyncio
async def test_swarm_service_owner_scope_and_session_relay(fake_db):
    _ = fake_db
    service = ResearchSwarmService()
    run = await service.create_run(
        principal=_principal(USER_A),
        preset="investment_committee",
        variables={"topic": "储能"},
        session_id="session-a",
    )

    assert run["status"] == "running"
    assert run["workers"]
    assert await service.get_run(run["run_id"], USER_B["id"]) is None
    assert [event["event_type"] for event in fake_db.research_events.documents] == [
        "swarm.started",
        "swarm.event",
        "swarm.event",
        "swarm.event",
        "swarm.event",
    ]

    cancelled = await service.cancel_run(run["run_id"], USER_A["id"])
    events = await service.list_events(run["run_id"], USER_A["id"], after_event_id=1)

    assert cancelled and cancelled["status"] == "cancelled"
    assert events[0]["event_type"] == "worker_queued"
    assert events[-1]["event_type"] == "run_cancelled"


@pytest.mark.asyncio
async def test_swarm_service_executes_workers_with_current_model_client(fake_db):
    _ = fake_db
    service = ResearchSwarmService()
    run = await service.create_run(
        principal=_principal(USER_A),
        preset="research_team",
        variables={"topic": "储能"},
        session_id="session-a",
    )

    completed = await service.execute_run(
        principal=_principal(USER_A),
        run_id=run["run_id"],
        model_client_factory=FakeWorkerModelClient,
    )

    assert completed and completed["status"] == "completed"
    assert completed["summaries"][0]["summary"] == "worker summary"
    assert "swarm.completed" in [
        event["event_type"] for event in fake_db.research_events.documents
    ]


@pytest.mark.asyncio
async def test_swarm_preset_contract_includes_quant_strategy_desk(fake_db):
    _ = fake_db
    service = ResearchSwarmService()
    presets = await service.list_presets()
    preset_names = {preset["preset"] for preset in presets}
    tool_schema_presets = set(
        ResearchToolRegistry.default().get("run_swarm").schema["properties"]["preset"]["enum"]
    )

    assert "quant_strategy_desk" in preset_names
    assert tool_schema_presets == {preset["preset"] for preset in DEFAULT_SWARM_PRESETS}


@pytest.mark.asyncio
async def test_swarm_routes_enforce_session_owner_and_retry(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.swarm_service = ResearchSwarmService(
        event_service=research_agent_router.event_service
    )

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="Swarm 会话"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    with pytest.raises(HTTPException) as owner_exc:
        await research_agent_router.create_swarm_run(
            research_agent_router.ResearchSwarmRunCreateRequest(
                preset="research_team", session_id=session_id
            ),
            current_user=USER_B,
        )

    run_response = await research_agent_router.create_swarm_run(
        research_agent_router.ResearchSwarmRunCreateRequest(
            preset="research_team",
            variables={"topic": "白酒"},
            session_id=session_id,
        ),
        current_user=USER_A,
    )
    run_id = run_response["data"]["run_id"]
    cancel_response = await research_agent_router.cancel_swarm_run(
        run_id, current_user=USER_A
    )
    retry_response = await research_agent_router.retry_swarm_run(
        run_id, current_user=USER_A
    )

    assert owner_exc.value.status_code == 404
    assert cancel_response["data"]["status"] == "cancelled"
    assert retry_response["data"]["parent_run_id"] == run_id


@pytest.mark.asyncio
async def test_run_swarm_tool_is_current_project_tool(fake_db, monkeypatch):
    _ = fake_db
    monkeypatch.setattr(swarm_module, "OpenAICompatibleModelClient", FakeWorkerModelClient)
    session = await ResearchSessionService().create_session(
        _principal(USER_A), title="Swarm 工具"
    )
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session["session_id"]),
        session_id=session["session_id"],
    )

    result = await registry.get("run_swarm").run(
        context, {"preset": "quant_strategy_desk", "variables": {"topic": "储能"}}
    )

    assert result["tool"] == "run_swarm"
    assert result["status"] == "completed"
    assert result["preset"] == "quant_strategy_desk"
    assert result["run_id"]
    assert result["summaries"][0]["summary"] == "worker summary"
    assert fake_db.research_swarm_runs.documents[0]["session_id"] == session["session_id"]
