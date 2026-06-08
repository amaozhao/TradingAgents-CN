from __future__ import annotations

from typing import Any

import pytest

from app.services.research_agent import events as events_module
from app.services.research_agent import sessions as sessions_module
from app.services.research_agent.context import ResearchPrincipal
from app.services.research_agent.loop import (
    ModelStreamChunk,
    ResearchAgentLoop,
    build_research_prompt,
)
from app.services.research_agent.registry import ResearchToolRegistry
from app.services.research_agent.sessions import ResearchSessionService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


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


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()


class FakeModelClient:
    def __init__(self, responses: list[list[ModelStreamChunk]]):
        self.responses = responses
        self.calls = 0

    async def stream(self, **_kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        for chunk in response:
            yield chunk


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(sessions_module, "get_postgres_db", lambda: db)
    monkeypatch.setattr(events_module, "get_postgres_db", lambda: db)
    return db


def _principal() -> ResearchPrincipal:
    return ResearchPrincipal.from_user(USER_A, session_id="session-a")


async def _create_session(fake_db) -> dict[str, Any]:
    _ = fake_db
    return await ResearchSessionService().create_session(_principal(), title="储能分析")


def test_prompt_uses_filtered_registry_tools_only():
    principal = _principal()
    tools = ResearchToolRegistry.default().for_principal(principal)
    prompt = build_research_prompt(principal=principal, tools=tools)

    assert "single_stock_analysis" in prompt
    assert "market_data_lookup" in prompt
    assert "admin_config_write" not in prompt
    assert "shell" not in prompt.lower()
    assert "file edit" not in prompt.lower()
    assert "live trading" not in prompt.lower()


@pytest.mark.asyncio
async def test_streamed_model_text_persists_events_and_final_message(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(delta="贵州茅台"),
                ModelStreamChunk(delta="维持关注。", finish_reason="stop"),
            ]
        ]
    )

    result = await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="分析贵州茅台",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]

    assert result["content"] == "贵州茅台维持关注。"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "贵州茅台维持关注。"
    assert event_types.count("assistant_delta") == 2
    assert "message_completed" in event_types
    assert "task_completed" in event_types


@pytest.mark.asyncio
async def test_tool_calls_create_tool_events_and_tool_messages(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(
                    tool_call={
                        "name": "single_stock_analysis",
                        "arguments": {"symbol": "600519"},
                    }
                ),
                ModelStreamChunk(delta="工具已完成。", finish_reason="stop"),
            ]
        ]
    )

    await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="调用工具分析",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]

    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    tool_messages = [message for message in messages if message["role"] == "tool"]
    assert tool_messages
    assert tool_messages[0]["metadata"]["tool_name"] == "single_stock_analysis"


@pytest.mark.asyncio
async def test_finish_reason_length_triggers_one_continuation(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [ModelStreamChunk(delta="第一段", finish_reason="length")],
            [ModelStreamChunk(delta="第二段", finish_reason="stop")],
        ]
    )

    result = await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="继续生成",
    )

    assert client.calls == 2
    assert result["content"] == "第一段第二段"
