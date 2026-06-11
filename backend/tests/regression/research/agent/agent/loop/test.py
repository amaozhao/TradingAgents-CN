from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import events as events_module
from app.services.research.agent import jobs as jobs_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.loop import (
    ModelStreamChunk,
    ResearchAgentLoop,
    build_research_prompt,
)
from app.services.research.agent.permissions import WEB_SEARCH
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.registry import ResearchTool
from app.services.research.agent.sessions import ResearchSessionService


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
        self.research_jobs = FakeCollection()
        self.research_attempts = FakeCollection()


class FakeModelClient:
    def __init__(self, responses: list[list[ModelStreamChunk]]):
        self.responses = responses
        self.calls = 0
        self.call_kwargs: list[dict[str, Any]] = []

    async def stream(self, **_kwargs):
        self.call_kwargs.append(_kwargs)
        response = self.responses[self.calls]
        self.calls += 1
        for chunk in response:
            yield chunk


class ExplodingModelClient:
    def __init__(self, *_args: Any, **_kwargs: Any):
        pass

    async def stream(self, **_kwargs):
        raise AssertionError("direct invocation must not call the model")
        yield ModelStreamChunk()


async def _fake_web_search(_context, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": "web_search",
        "status": "completed",
        "query": payload.get("query"),
        "results": [{"title": "FOMC minutes", "snippet": "Rates remain restrictive."}],
    }


async def _fake_stock_analysis(_context, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status_override") == "failed":
        return {
            "tool": "stock_analysis",
            "mode": payload.get("mode") or "single",
            "status": "failed",
            "accepted": True,
            "task_id": "task-600519",
            "symbol": payload.get("symbol"),
            "market_type": payload.get("market_type"),
            "progress": 35,
            "task_url": "/tasks?task_id=task-600519",
            "report_url": "/reports/view/task-600519",
            "error_message": "行情数据源无可用历史数据。",
        }
    if payload.get("status_override") == "timed_out":
        return {
            "tool": "stock_analysis",
            "mode": payload.get("mode") or "single",
            "status": "processing",
            "accepted": True,
            "wait_timed_out": True,
            "task_id": "task-600519",
            "symbol": payload.get("symbol"),
            "market_type": payload.get("market_type"),
            "progress": 40,
            "task_url": "/tasks?task_id=task-600519",
            "report_url": "/reports/view/task-600519",
            "message": "单股分析任务仍在执行，已返回任务链接。",
        }
    result = {
        "tool": "stock_analysis",
        "mode": payload.get("mode") or "single",
        "status": "queued",
        "accepted": True,
        "task_id": "task-600519",
        "symbol": payload.get("symbol"),
        "market_type": payload.get("market_type"),
        "task_url": "/tasks?task_id=task-600519",
        "report_url": "/reports/view/task-600519",
        "message": "单股分析任务已提交。",
    }
    if payload.get("include_stage_plan"):
        result["stage_plan"] = [
            {"stage": "prepare_data", "title": "数据准备", "status": "pending"},
            {"stage": "market_analysis", "title": "市场分析师", "status": "pending"},
            {
                "stage": "fundamentals_analysis",
                "title": "基本面分析师",
                "status": "skipped",
                "reason": "未选择该分析师。",
            },
            {
                "stage": "risk_review",
                "title": "风险评估",
                "status": "skipped",
                "reason": "用户关闭风险评估。",
            },
            {"stage": "agent_summary", "title": "Agent 总结", "status": "pending"},
        ]
    return result


def _web_search_registry() -> ResearchToolRegistry:
    return ResearchToolRegistry(
        [
            ResearchTool(
                name="web_search",
                description="搜索公开网页资料",
                permission=WEB_SEARCH,
                schema={"type": "object", "required": ["query"]},
                handler=_fake_web_search,
            )
        ]
    )


def _stock_registry() -> ResearchToolRegistry:
    return ResearchToolRegistry(
        [
            ResearchTool(
                name="stock_analysis",
                description="Submit a single-stock analysis workflow.",
                permission=WEB_SEARCH,
                schema={
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string"},
                        "symbol": {"type": "string"},
                        "market_type": {"type": "string"},
                    },
                },
                handler=_fake_stock_analysis,
            )
        ]
    )


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(sessions_module, "get_postgres_db", lambda: db)
    monkeypatch.setattr(events_module, "get_postgres_db", lambda: db)
    monkeypatch.setattr(jobs_module, "get_postgres_db", lambda: db)
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

    assert "stock_analysis" in prompt
    assert "single_stock_analysis" in prompt
    assert "stock_analysis_status" in prompt
    assert "stock_analysis_report" in prompt
    assert "stock_analysis submits a single-stock analysis" in prompt
    assert "without modifying DAG internals" in prompt
    assert (
        "single_stock_analysis submits the existing single-stock LangGraph DAG"
        in prompt
    )
    assert "waits for the report by default" in prompt
    assert "market_data_lookup" in prompt
    assert "admin_config_write" not in prompt
    assert "shell" not in prompt.lower()
    assert "file edit" not in prompt.lower()
    assert "live trading" not in prompt.lower()


def test_prompt_blocks_shadow_and_journal_calls_without_owner_data():
    principal = _principal()
    tools = ResearchToolRegistry.default().for_principal(principal)
    prompt = build_research_prompt(principal=principal, tools=tools)

    assert "Do not call analyze_trade_journal" in prompt
    assert "Do not call run_shadow_backtest" in prompt
    assert "ask the user to upload or paste the missing data" in prompt


def test_prompt_blocks_trading_reads_until_connector_is_connected():
    principal = _principal()
    tools = ResearchToolRegistry.default().for_principal(principal)
    prompt = build_research_prompt(principal=principal, tools=tools)

    assert "Call trading_check before trading_account" in prompt
    assert "Do not call trading_account" in prompt
    assert "status is connected" in prompt


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
                ModelStreamChunk(reasoning_content="先调用工具确认证据。"),
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
async def test_tool_events_are_scoped_to_attempt_id(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-1",
                        "name": "single_stock_analysis",
                        "arguments": {"symbol": "600519"},
                    },
                    finish_reason="tool_calls",
                ),
            ],
            [ModelStreamChunk(delta="完成。", finish_reason="stop")],
        ]
    )

    await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="调用工具分析",
        attempt_id="attempt-tool-scope",
    )
    tool_events = [
        event
        for event in fake_db.research_events.documents
        if event["event_type"] in {"tool_started", "tool_completed"}
    ]

    assert tool_events
    assert {event["payload"].get("attempt_id") for event in tool_events} == {
        "attempt-tool-scope"
    }


@pytest.mark.asyncio
async def test_tool_call_finish_reason_continues_react_loop(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(reasoning_content="先调用工具确认证据。"),
                ModelStreamChunk(
                    tool_call={
                        "id": "call-1",
                        "name": "single_stock_analysis",
                        "arguments": {"symbol": "600519"},
                        "thought_signature": "sig-1",
                    },
                    finish_reason="tool_calls",
                ),
            ],
            [
                ModelStreamChunk(delta="工具证据已纳入。", finish_reason="stop"),
            ],
        ]
    )

    result = await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="调用工具后继续回答",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    assistant_tool_calls = [
        message
        for message in messages
        if message["role"] == "assistant" and message["metadata"].get("tool_calls")
    ]
    tool_messages = [message for message in messages if message["role"] == "tool"]

    assert client.calls == 2
    assert result["content"] == "工具证据已纳入。"
    assert assistant_tool_calls[0]["metadata"]["tool_calls"][0]["id"] == "call-1"
    assert assistant_tool_calls[0]["metadata"]["tool_calls"][0]["extra_content"] == {
        "google": {"thought_signature": "sig-1"}
    }
    assert (
        assistant_tool_calls[0]["metadata"]["reasoning_content"]
        == "先调用工具确认证据。"
    )
    assert tool_messages[0]["metadata"]["tool_call_id"] == "call-1"
