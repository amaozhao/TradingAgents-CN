from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import events as events_module
from app.services.research.agent import jobs as jobs_module
from app.services.research.agent import runtime as runtime_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.loop import (
    EMPTY_FINAL_ANSWER_FALLBACK,
    ModelStreamChunk,
    ResearchAgentCancelled,
    ResearchAgentLoop,
)
from app.services.research.agent.permissions import WEB_SEARCH
from app.services.research.agent.registry import ResearchTool, ResearchToolRegistry
from app.services.research.agent.runtime import ResearchAgentRuntime
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


@pytest.mark.asyncio
async def test_structured_metadata_direct_invocation_bypasses_model(
    fake_db, monkeypatch
):
    monkeypatch.setattr(
        runtime_module, "OpenAICompatibleModelClient", ExplodingModelClient
    )
    session = await _create_session(fake_db)
    runtime = ResearchAgentRuntime(registry=_stock_registry())
    metadata = {
        "source": "research-agent-page",
        "mode": "stock_analysis_workflow",
        "tool_name": "stock_analysis",
        "tool_arguments": {
            "mode": "single",
            "symbol": "600519",
            "market_type": "A股",
            "wait_for_completion": False,
        },
    }

    queued = await runtime.enqueue_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        metadata=metadata,
    )
    result = await runtime.run_queued_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        job_id=queued["job_id"],
        attempt_id=queued["attempt_id"],
        metadata=metadata,
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]
    stage_events = [
        event
        for event in fake_db.research_events.documents
        if event["event_type"] == "stock_analysis.stage"
    ]
    tool_messages = [message for message in messages if message["role"] == "tool"]

    assert result["status"] == "completed"
    assert result["finish_reason"] == "direct_tool"
    assert result["reason"] == "structured_metadata_direct_tool"
    assert result["task_ids"] == ["task-600519"]
    assert tool_messages[0]["metadata"]["tool_name"] == "stock_analysis"
    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    assert "stock_analysis.stage" in event_types
    assert "message_completed" in event_types
    assert [event["payload"]["stage"] for event in stage_events] == [
        "validate_input",
        "analysis_task",
    ]
    assert {event["payload"]["attempt_id"] for event in stage_events} == {
        queued["attempt_id"]
    }
    assert stage_events[0]["payload"]["status"] == "running"
    assert stage_events[0]["payload"]["progress"] == 5
    assert stage_events[0]["payload"]["title"] == "参数校验"
    assert stage_events[1]["payload"]["title"] == "单股分析任务"
    assert stage_events[1]["payload"]["task_id"] == "task-600519"
    assert stage_events[1]["payload"]["report_url"] == "/reports/view/task-600519"
    assert all(event["payload"]["started_at"] for event in stage_events)
    assert all("completed_at" in event["payload"] for event in stage_events)


@pytest.mark.asyncio
async def test_structured_metadata_direct_invocation_persists_stage_plan(
    fake_db, monkeypatch
):
    monkeypatch.setattr(
        runtime_module, "OpenAICompatibleModelClient", ExplodingModelClient
    )
    session = await _create_session(fake_db)
    runtime = ResearchAgentRuntime(registry=_stock_registry())
    metadata = {
        "source": "research-agent-page",
        "mode": "stock_analysis_workflow",
        "tool_name": "stock_analysis",
        "tool_arguments": {
            "mode": "single",
            "symbol": "600519",
            "market_type": "A股",
            "wait_for_completion": False,
            "include_stage_plan": True,
        },
    }

    queued = await runtime.enqueue_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        metadata=metadata,
    )
    await runtime.run_queued_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        job_id=queued["job_id"],
        attempt_id=queued["attempt_id"],
        metadata=metadata,
    )
    stage_events = [
        event["payload"]
        for event in fake_db.research_events.documents
        if event["event_type"] == "stock_analysis.stage"
    ]

    assert [event["stage"] for event in stage_events] == [
        "validate_input",
        "prepare_data",
        "market_analysis",
        "fundamentals_analysis",
        "risk_review",
        "analysis_task",
    ]
    assert stage_events[1]["status"] == "pending"
    assert stage_events[2]["title"] == "市场分析师"
    assert stage_events[3]["status"] == "skipped"
    assert stage_events[3]["message"] == "未选择该分析师。"
    assert stage_events[3]["completed_at"]
    assert stage_events[4]["status"] == "skipped"
    assert stage_events[4]["message"] == "用户关闭风险评估。"
    assert stage_events[4]["completed_at"]
    assert stage_events[-1]["started_at"]
    assert stage_events[-1]["completed_at"] is None
    assert {event["attempt_id"] for event in stage_events} == {queued["attempt_id"]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_override", "terminal_event", "expected_content", "forbidden_content"),
    [
        (
            "failed",
            "stock_analysis.failed",
            "行情数据源无可用历史数据。",
            "工具已完成",
        ),
        (
            "timed_out",
            "stock_analysis.timed_out",
            "单股分析任务仍在执行，已返回任务链接。",
            "工具已完成",
        ),
    ],
)
async def test_structured_metadata_direct_invocation_preserves_non_completed_status(
    fake_db,
    monkeypatch,
    status_override,
    terminal_event,
    expected_content,
    forbidden_content,
):
    monkeypatch.setattr(
        runtime_module, "OpenAICompatibleModelClient", ExplodingModelClient
    )
    session = await _create_session(fake_db)
    runtime = ResearchAgentRuntime(registry=_stock_registry())
    metadata = {
        "source": "research-agent-page",
        "mode": "stock_analysis_workflow",
        "tool_name": "stock_analysis",
        "tool_arguments": {
            "mode": "single",
            "symbol": "600519",
            "market_type": "A股",
            "status_override": status_override,
        },
    }

    queued = await runtime.enqueue_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        metadata=metadata,
    )
    result = await runtime.run_queued_user_prompt(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="单股分析：600519 / A股",
        job_id=queued["job_id"],
        attempt_id=queued["attempt_id"],
        metadata=metadata,
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]
    stage_events = [
        event["payload"]
        for event in fake_db.research_events.documents
        if event["event_type"] == "stock_analysis.stage"
    ]

    assert expected_content in result["content"]
    assert forbidden_content not in result["content"]
    assert terminal_event in event_types
    assert "stock_analysis.completed" not in event_types
    assert stage_events[-1]["stage"] in {"analysis_task", "wait_bounded"}
    assert stage_events[-1]["status"] in {"failed", "running"}


@pytest.mark.asyncio
async def test_completed_tool_run_forces_visible_final_answer_when_model_stops_empty(
    fake_db,
):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-search",
                        "name": "web_search",
                        "arguments": {"query": "FOMC minutes April 2026"},
                    },
                    finish_reason="tool_calls",
                ),
            ],
            [ModelStreamChunk(finish_reason="stop")],
            [
                ModelStreamChunk(
                    delta="搜索结果显示会议纪要偏谨慎。", finish_reason="stop"
                )
            ],
        ]
    )

    result = await ResearchAgentLoop(
        model_client=client,
        registry=_web_search_registry(),
    ).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="请读取最新的美联储会议纪要并总结影响",
        attempt_id="attempt-final",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    message_completed = [
        event
        for event in fake_db.research_events.documents
        if event["event_type"] == "message_completed"
    ][0]

    assert client.calls == 3
    assert result["content"] == "搜索结果显示会议纪要偏谨慎。"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "搜索结果显示会议纪要偏谨慎。"
    assert message_completed["payload"]["content"] == "搜索结果显示会议纪要偏谨慎。"


@pytest.mark.asyncio
async def test_completed_attempt_never_persists_blank_assistant_message(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-search",
                        "name": "web_search",
                        "arguments": {"query": "FOMC minutes April 2026"},
                    },
                    finish_reason="tool_calls",
                ),
            ],
            [ModelStreamChunk(finish_reason="stop")],
            [ModelStreamChunk(finish_reason="stop")],
        ]
    )

    result = await ResearchAgentLoop(
        model_client=client,
        registry=_web_search_registry(),
    ).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="请读取最新的美联储会议纪要并总结影响",
        attempt_id="attempt-fallback",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    message_completed = [
        event
        for event in fake_db.research_events.documents
        if event["event_type"] == "message_completed"
    ][0]

    assert result["content"] == EMPTY_FINAL_ANSWER_FALLBACK
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == EMPTY_FINAL_ANSWER_FALLBACK
    assert message_completed["payload"]["content"] == EMPTY_FINAL_ANSWER_FALLBACK


@pytest.mark.asyncio
async def test_missing_tool_argument_returns_config_required_without_failing_attempt(
    fake_db,
):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-shadow",
                        "name": "extract_shadow_strategy",
                        "arguments": {},
                    },
                    finish_reason="tool_calls",
                ),
            ],
            [
                ModelStreamChunk(
                    delta="已根据现有证据继续总结。", finish_reason="stop"
                ),
            ],
        ]
    )

    result = await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="请基于沪深300构建多因子模型",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]
    tool_messages = [message for message in messages if message["role"] == "tool"]

    assert client.calls == 2
    assert result["content"] == "已根据现有证据继续总结。"
    assert "tool_completed" in event_types
    assert "tool_failed" not in event_types
    assert "task_failed" not in event_types
    assert "message_completed" in event_types
    assert tool_messages[0]["metadata"]["tool_name"] == "extract_shadow_strategy"
    assert '"status": "config_required"' in tool_messages[0]["content"]
    assert "description is required" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_reasoning_chunks_are_logged_and_saved_in_final_metadata(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(reasoning_content="先看上下文。"),
                ModelStreamChunk(delta="最终回答。", finish_reason="stop"),
            ]
        ]
    )

    await ResearchAgentLoop(model_client=client).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="解释能力",
    )
    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    log_events = [
        event
        for event in fake_db.research_events.documents
        if event["event_type"] == "log"
    ]

    assert log_events[0]["payload"] == {
        "kind": "reasoning",
        "content": "先看上下文。",
        "attempt_id": None,
    }
    assert messages[-1]["metadata"]["reasoning_content"] == "先看上下文。"


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


@pytest.mark.asyncio
async def test_loop_stops_when_cancel_checker_trips_mid_stream(fake_db):
    session = await _create_session(fake_db)
    client = FakeModelClient(
        [
            [
                ModelStreamChunk(delta="第一段"),
                ModelStreamChunk(delta="不应写入", finish_reason="stop"),
            ]
        ]
    )
    checks = 0

    async def cancel_after_first_chunk() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    with pytest.raises(ResearchAgentCancelled):
        await ResearchAgentLoop(
            model_client=client,
            cancel_checker=cancel_after_first_chunk,
        ).run(
            principal=_principal(),
            session_id=session["session_id"],
            user_message="取消测试",
            attempt_id="attempt-cancel",
        )

    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    event_types = [event["event_type"] for event in fake_db.research_events.documents]

    assert "task_failed" in event_types
    assert messages[-1]["role"] == "user"
    assert all(message["content"] != "第一段不应写入" for message in messages)


@pytest.mark.asyncio
async def test_context_compaction_emits_event_and_collapses_old_messages(fake_db):
    session = await _create_session(fake_db)
    long_content = "旧研究上下文" * 500
    await ResearchSessionService().append_message(
        session_id=session["session_id"],
        user_id=USER_A["id"],
        role="assistant",
        content=long_content,
    )
    client = FakeModelClient(
        [[ModelStreamChunk(delta="已压缩上下文。", finish_reason="stop")]]
    )

    await ResearchAgentLoop(
        model_client=client,
        context_char_budget=900,
        preserve_recent_messages=1,
    ).run(
        principal=_principal(),
        session_id=session["session_id"],
        user_message="继续",
    )

    event_types = [event["event_type"] for event in fake_db.research_events.documents]
    outbound_messages = client.call_kwargs[0]["messages"]
    outbound_content = "\n".join(
        str(message.get("content") or "") for message in outbound_messages
    )

    assert "compact" in event_types
    assert "compacted for context budget" in outbound_content
    assert long_content not in outbound_content
