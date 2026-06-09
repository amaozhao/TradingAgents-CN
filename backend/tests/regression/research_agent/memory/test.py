from __future__ import annotations

from typing import Any

import pytest

from app.services.research_agent import memory as memory_module
from app.services.research_agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research_agent.registry import ResearchToolRegistry


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

    async def find_one(self, query: dict[str, Any], *_args: Any, **_kwargs: Any):
        rows = [doc for doc in self.documents if _matches_query(doc, query)]
        return dict(rows[0]) if rows else None

    def find(self, query: dict[str, Any]):
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                document.update(update.get("$set", {}))
                return type("FakeUpdateResult", (), {"modified_count": 1})()
        return type("FakeUpdateResult", (), {"modified_count": 0})()


class FakeDb:
    def __init__(self):
        self.research_agent_memory = FakeCollection()
        self.research_hypotheses = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(memory_module, "get_postgres_db", lambda db=db: db)
    return db


def _context(user: dict[str, Any]) -> ToolExecutionContext:
    return ToolExecutionContext(
        principal=ResearchPrincipal.from_user(user, session_id="session-memory"),
        session_id="session-memory",
    )


@pytest.mark.asyncio
async def test_memory_and_hypothesis_tools_are_owner_scoped(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()

    memory = await registry.get("remember").run(
        _context(USER_A), {"content": "Prefer evidence-backed risk notes"}
    )
    hypothesis = await registry.get("create_hypothesis").run(
        _context(USER_A),
        {"title": "储能 momentum", "thesis": "储能龙头延续强势"},
    )
    hypothesis_id = hypothesis["hypothesis"]["hypothesis_id"]
    updated = await registry.get("update_hypothesis").run(
        _context(USER_A), {"hypothesis_id": hypothesis_id, "status": "validated"}
    )
    linked = await registry.get("link_backtest").run(
        _context(USER_A), {"hypothesis_id": hypothesis_id, "backtest_id": "bt-1"}
    )
    matches = await registry.get("search_hypotheses").run(
        _context(USER_A), {"query": "momentum"}
    )
    other_matches = await registry.get("search_hypotheses").run(
        _context(USER_B), {"query": "momentum"}
    )

    assert memory["memory"]["content"].startswith("Prefer")
    assert updated["hypothesis"]["status"] == "validated"
    assert linked["hypothesis"]["linked_backtests"][0]["backtest_id"] == "bt-1"
    assert matches["matches"][0]["hypothesis_id"] == hypothesis_id
    assert other_matches["matches"] == []
