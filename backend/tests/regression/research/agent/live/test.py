from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers.research import agent as research_agent_router
from app.services.research.agent import events as events_module
from app.services.research.agent import live as live_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.events import ResearchEventService
from app.services.research.agent.live import LivePermissionError, LiveSafetyError, LiveSafetyService
from app.services.research.agent.registry import ResearchToolRegistry


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
ADMIN = {"id": "admin-a", "username": "root", "is_admin": True, "roles": ["admin"]}


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

    async def find_one(self, query: dict[str, Any], *_args: Any, **_kwargs: Any):
        rows = [doc for doc in self.documents if _matches_query(doc, query)]
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
        self.research_live_state = FakeCollection()
        self.research_live_audit = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, live_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any], session_id: str | None = "session-live"):
    return ResearchPrincipal.from_user(user, session_id=session_id)


@pytest.mark.asyncio
async def test_live_service_is_permissioned_and_fail_closed(fake_db):
    _ = fake_db
    service = LiveSafetyService()

    with pytest.raises(LivePermissionError):
        await service.halt(principal=_principal(USER), reason="test", session_id=None)
    with pytest.raises(LiveSafetyError):
        await service.runner_start(principal=_principal(ADMIN), broker="paper")

    proposal = await service.propose_mandate(
        principal=_principal(USER),
        session_id="session-live",
        constraints={"max_notional": 1000},
    )
    mandate = await service.commit_mandate(
        principal=_principal(ADMIN),
        session_id="session-live",
        proposal=proposal,
    )
    await service.authorize(principal=_principal(ADMIN), broker="paper", session_id="session-live")
    runner = await service.runner_start(
        principal=_principal(ADMIN), broker="paper", session_id="session-live"
    )

    assert proposal["status"] == "proposed"
    assert mandate["expired"] is False
    assert runner["alive"] is True
    assert [event["event_type"] for event in fake_db.research_events.documents] == [
        "mandate.proposed",
        "mandate.committed",
        "live.action",
        "live.action",
    ]


@pytest.mark.asyncio
async def test_live_routes_require_admin_for_mutation(fake_db):
    _ = fake_db
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.live_service = LiveSafetyService(
        event_service=research_agent_router.event_service
    )

    status_response = await research_agent_router.get_live_status(current_user=USER)
    with pytest.raises(HTTPException) as halt_exc:
        await research_agent_router.halt_live_runtime(
            research_agent_router.LiveActionRequest(reason="test"),
            current_user=USER,
        )
    halt_response = await research_agent_router.halt_live_runtime(
        research_agent_router.LiveActionRequest(reason="admin halt"),
        current_user=ADMIN,
    )

    assert status_response["data"]["global_halted"] is False
    assert halt_exc.value.status_code == 403
    assert halt_response["data"]["halted"] is True


@pytest.mark.asyncio
async def test_live_tools_are_readonly_and_mandate_proposal_only(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=_principal(USER),
        session_id="session-live",
    )

    connections = await registry.get("trading_connections").run(context, {})
    selected = await registry.get("trading_select_connection").run(context, {"broker": "paper"})
    check = await registry.get("trading_check").run(context, {"broker": "paper"})
    positions = await registry.get("trading_positions").run(context, {})
    proposal = await registry.get("propose_mandate_profiles").run(
        context, {"constraints": {"max_notional": 1000}}
    )
    place_order = await registry.get("trading_place_order").run(
        ToolExecutionContext(principal=_principal(ADMIN), session_id="session-live"),
        {"symbol": "AAPL"},
    )

    assert connections["profiles"][0]["oauth_token_present"] is False
    assert selected["selected"] is True
    assert selected["live_trading_enabled"] is False
    assert check["read_only"] is True
    assert positions["live_trading_enabled"] is False
    assert proposal["status"] == "proposed"
    assert place_order["accepted"] is False
