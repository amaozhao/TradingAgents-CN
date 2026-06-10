from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks
from fastapi import HTTPException

from app.routers.research import agent as research_agent_router
from app.services.research.agent import artifacts as artifacts_module
from app.services.research.agent import events as events_module
from app.services.research.agent.tools import files as files_module
from app.services.research.agent.tools import correlation as correlation_module
from app.services.research.agent.tools.market import data as market_data_module
from app.services.research.agent.tools import quant as quant_module
from app.services.research.agent.tools import shadow as shadow_module
from app.services.research.agent.tools import journal as journal_module
from app.services.research.agent.tools import memory as memory_tools_module
from app.services.research.agent import jobs as jobs_module
from app.services.research.agent import live as live_module
from app.services.research.agent import memory as research_memory_module
from app.services.research.agent import runtime as runtime_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent.artifacts import ResearchArtifactService
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.events import ResearchEventService
from app.services.research.agent.loop import ModelStreamChunk, ResearchAgentLoop
from app.services.research.agent.sessions import ResearchSessionService


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

    async def delete_one(self, query: dict[str, Any]):
        for index, document in enumerate(self.documents):
            if _matches_query(document, query):
                del self.documents[index]
                return type("FakeDeleteResult", (), {"deleted_count": 1})()
        return type("FakeDeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, query: dict[str, Any]):
        before = len(self.documents)
        self.documents = [
            document for document in self.documents if not _matches_query(document, query)
        ]
        return type(
            "FakeDeleteResult", (), {"deleted_count": before - len(self.documents)}
        )()


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()
        self.research_jobs = FakeCollection()
        self.research_attempts = FakeCollection()
        self.research_goals = FakeCollection()
        self.research_hypotheses = FakeCollection()
        self.research_memory = FakeCollection()
        self.research_live_state = FakeCollection()
        self.research_live_audit = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, artifacts_module, jobs_module, live_module, research_memory_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any]) -> ResearchPrincipal:
    return ResearchPrincipal.from_user(user, session_id="request-session")


def test_runtime_exception_message_falls_back_to_exception_name():
    assert (
        runtime_module._exception_message(TimeoutError())
        == "外部模型或网络服务请求超时（TimeoutError）"
    )


def test_runtime_exception_message_humanizes_blank_timeout_name():
    class ConnectTimeout(Exception):
        pass

    assert (
        runtime_module._exception_message(ConnectTimeout())
        == "外部模型或网络服务请求超时（ConnectTimeout）"
    )


@pytest.mark.asyncio
async def test_web_search_timeout_degrades_instead_of_raising(monkeypatch):
    class TimeoutClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, *args: Any, **kwargs: Any):
            raise files_module.httpx.ConnectTimeout("connect timed out")

    monkeypatch.setattr(files_module.httpx, "AsyncClient", TimeoutClient)

    result = await files_module._web_search(
        ToolExecutionContext(
            principal=_principal(USER_A),
            session_id="session-1",
            request_id="attempt-1",
        ),
        {"query": "A股储能", "limit": 3},
    )

    assert result["status"] == "degraded"
    assert result["tool"] == "web_search"
    assert result["error_type"] == "ConnectTimeout"
    assert result["results"] == []
    assert "不要编造搜索结果" in result["instruction"]


def _sample_series(symbols: list[str]) -> dict[str, dict[str, Any]]:
    base_map = {
        "000001": [10.0, 10.2, 10.1, 10.4, 10.6],
        "AAPL": [200.0, 201.0, 199.5, 203.0, 204.0],
        "BTC-USDT": [65000.0, 66000.0, 65500.0, 67000.0, 68000.0],
        "600519": [1500.0, 1510.0, 1498.0, 1520.0, 1530.0],
        "300750": [200.0, 198.0, 202.0, 205.0, 206.0],
    }
    out: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        prices = base_map.get(symbol, [1.0, 1.01, 1.02, 1.03, 1.04])
        rows = [
            {"date": f"2026-01-0{index + 1}", "close": close}
            for index, close in enumerate(prices)
        ]
        returns = [
            prices[index] / prices[index - 1] - 1
            for index in range(1, len(prices))
        ]
        out[symbol] = {
            "symbol": symbol,
            "market": "CN" if symbol.isdigit() else "US",
            "source": "test",
            "prices": rows,
            "returns": returns,
            "observations": len(rows),
            "status": "completed",
        }
    return out


@pytest.mark.asyncio
async def test_market_data_lookup_returns_structured_snapshot(monkeypatch):
    async def fake_lookup(symbol: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "market": "CN",
            "basic_info": {"code": symbol, "name": "平安银行"},
            "quote": {"close": 10.6},
            "history": _sample_series([symbol])[symbol],
            "status": "completed",
        }

    monkeypatch.setattr(market_data_module, "lookup_market_snapshot", fake_lookup)

    result = await market_data_module._market_data_lookup(
        ToolExecutionContext(principal=_principal(USER_A)),
        {"symbol": "000001.SZ", "start_date": "2026-01-01", "end_date": "2026-01-05"},
    )

    assert result["tool"] == "market_data_lookup"
    assert result["status"] == "completed"
    assert result["symbol"] == "000001"
    assert result["basic_info"]["name"] == "平安银行"
    assert result["history"]["observations"] == 5


@pytest.mark.asyncio
async def test_backtest_accepts_symbols_and_persists_metrics(fake_db, monkeypatch):
    async def fake_series(symbols: list[str], **_kwargs: Any) -> dict[str, dict[str, Any]]:
        return _sample_series(symbols)

    monkeypatch.setattr(quant_module, "load_price_series", fake_series)
    context = ToolExecutionContext(
        principal=_principal(USER_A),
        session_id="session-backtest",
    )

    result = await quant_module._backtest(
        context,
        {
            "symbols": {"item": ["000001.SZ", "BTC-USDT", "AAPL"]},
            "start_date": "2026-01-01",
            "end_date": "2026-01-05",
            "optimizer": "risk_parity",
        },
    )

    assert result["status"] == "completed"
    assert result["symbols"] == ["000001", "BTC-USDT", "AAPL"]
    assert result["metrics"]["observations"] == 4
    assert set(result["weights"]) == {"000001", "BTC-USDT", "AAPL"}
    assert result["artifact_id"]
    assert fake_db.research_artifacts.documents[-1]["artifact_type"] == "backtest_run"


@pytest.mark.asyncio
async def test_backtest_accepts_alias_symbol_shapes(fake_db, monkeypatch):
    async def fake_series(symbols: list[str], **_kwargs: Any) -> dict[str, dict[str, Any]]:
        return _sample_series(symbols)

    monkeypatch.setattr(quant_module, "load_price_series", fake_series)
    context = ToolExecutionContext(
        principal=_principal(USER_A),
        session_id="session-backtest-alias",
    )

    result = await quant_module._backtest(
        context,
        {
            "portfolio": {
                "assets": [
                    {"ticker": "000001.SZ"},
                    {"symbol": "BTC-USDT"},
                    {"code": "AAPL"},
                ]
            },
            "start_date": "2026-01-01",
            "end_date": "2026-01-05",
        },
    )

    assert result["status"] == "completed"
    assert result["symbols"] == ["000001", "BTC-USDT", "AAPL"]
    assert result["metrics"]["observations"] == 4


@pytest.mark.asyncio
async def test_correlation_matrix_prefers_market_series(fake_db, monkeypatch):
    async def fake_series(symbols: list[str], **_kwargs: Any) -> dict[str, dict[str, Any]]:
        return _sample_series(symbols)

    monkeypatch.setattr(correlation_module, "load_price_series", fake_series)
    job = await correlation_module.ResearchMatrixJobService().create_correlation_job(
        principal=_principal(USER_A),
        symbols=["600519", "000001", "300750"],
        window=5,
    )

    result = job["result"]
    assert result["matrix_source"] == "market_data"
    assert set(result["matrix"]) == {"600519", "000001", "300750"}
    assert result["missing_symbols"] == []
    assert result["artifact_id"]


@pytest.mark.asyncio
async def test_shadow_and_trade_journal_examples_have_enough_inputs(fake_db):
    context = ToolExecutionContext(
        principal=_principal(USER_A),
        session_id="session-shadow",
    )

    strategy = await shadow_module._extract_shadow_strategy(
        context,
        {"description": "buy momentum breakouts after volume expansion and exit on failed retest"},
    )
    backtest = await shadow_module._run_shadow_backtest(
        context,
        {
            "strategy_id": strategy["strategy_id"],
            "returns": {"item": [0.018, -0.007, 0.024, -0.011, 0.009, 0.015, -0.006]},
        },
    )
    report = await shadow_module._render_shadow_report(
        context,
        {
            "strategy_id": strategy["strategy_id"],
            "backtest_id": backtest["backtest_id"],
            "summary": "sample shadow report",
        },
    )
    journal = await journal_module._analyze_trade_journal(
        context,
        {
            "text": "\n".join(
                [
                    "2026-05-06 600519.SH buy after breakout, pnl +1200, followed plan.",
                    "2026-05-09 300750.SZ revenge trade after loss, pnl -1800, violated stop loss.",
                    "2026-05-12 AAPL chased open gap, pnl -350, overtrade.",
                    "2026-05-14 BTC-USD reduced size, pnl +420, respected risk limit.",
                ]
            )
        },
    )

    assert strategy["status"] == "completed"
    assert backtest["status"] == "completed"
    assert report["status"] == "completed"
    assert journal["status"] == "completed"
    assert journal["metrics"]["trades_with_pnl"] == 4
    assert journal["metrics"]["risk_flag_count"] >= 2


@pytest.mark.asyncio
async def test_create_hypothesis_accepts_vibe_style_statement(fake_db):
    _ = fake_db
    result = await memory_tools_module._create_hypothesis(
        ToolExecutionContext(
            principal=_principal(USER_A),
            session_id="session-hypothesis",
        ),
        {
            "statement": "A 股储能板块在大储放量下具备阶段性机会",
            "rationale": "国内招标回升，海外户储去库接近尾声。",
            "tags": {"item": ["储能", "A股"]},
        },
    )

    assert result["status"] == "completed"
    assert result["hypothesis"]["title"] == "A 股储能板块在大储放量下具备阶段性机会"
    assert "大储放量" in result["hypothesis"]["thesis"]


class FakeProviderModelClient:
    calls = 0

    def __init__(self, _principal: ResearchPrincipal) -> None:
        return None

    async def stream(self, **_kwargs: Any):
        responses = [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-screen",
                        "name": "screening_run",
                        "arguments": {
                            "sector": "储能",
                            "symbols": ["300750.SZ", "002594.SZ"],
                        },
                    },
                    finish_reason="tool_calls",
                )
            ],
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-analysis",
                        "name": "single_stock_analysis",
                        "arguments": {"symbol": "300750.SZ"},
                    },
                    finish_reason="tool_calls",
                )
            ],
            [ModelStreamChunk(delta="基于工具证据，储能板块优先关注 300750.SZ。", finish_reason="stop")],
        ]
        response = responses[FakeProviderModelClient.calls]
        FakeProviderModelClient.calls += 1
        for chunk in response:
            yield chunk


class ConnectorProviderModelClient:
    calls = 0

    def __init__(self, _principal: ResearchPrincipal) -> None:
        return None

    async def stream(self, **_kwargs: Any):
        responses = [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-connector",
                        "name": "trading_check",
                        "arguments": {"broker": "paper"},
                    },
                    finish_reason="tool_calls",
                )
            ],
            [ModelStreamChunk(delta="交易连接器检查完成：当前为只读研究模式。", finish_reason="stop")],
        ]
        response = responses[ConnectorProviderModelClient.calls]
        ConnectorProviderModelClient.calls += 1
        for chunk in response:
            yield chunk


class RiskParityProviderModelClient:
    calls = 0

    def __init__(self, _principal: ResearchPrincipal) -> None:
        return None

    async def stream(self, **_kwargs: Any):
        responses = [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-backtest",
                        "name": "backtest",
                        "arguments": {
                            "returns": [0.01, -0.004, 0.006, 0.003],
                            "signals": [1, 1, 1, 1],
                        },
                    },
                    finish_reason="tool_calls",
                )
            ],
            [
                ModelStreamChunk(
                    delta="跨市场风险平价风格回测已完成，结果基于工具输出，不使用占位结论。",
                    finish_reason="stop",
                )
            ],
        ]
        response = responses[RiskParityProviderModelClient.calls]
        RiskParityProviderModelClient.calls += 1
        for chunk in response:
            yield chunk


class EmptyBacktestArgumentsModelClient:
    calls = 0

    def __init__(self, _principal: ResearchPrincipal) -> None:
        return None

    async def stream(self, **_kwargs: Any):
        responses = [
            [
                ModelStreamChunk(
                    tool_call={
                        "id": "call-empty-backtest",
                        "name": "backtest",
                        "arguments": {},
                    },
                    finish_reason="tool_calls",
                )
            ],
            [
                ModelStreamChunk(
                    delta="回测完成，已基于用户请求中的 symbols 和日期运行。",
                    finish_reason="stop",
                )
            ],
        ]
        response = responses[EmptyBacktestArgumentsModelClient.calls]
        EmptyBacktestArgumentsModelClient.calls += 1
        for chunk in response:
            yield chunk


class TextOnlyProviderModelClient:
    def __init__(self, _principal: ResearchPrincipal) -> None:
        return None

    async def stream(self, **_kwargs: Any):
        yield ModelStreamChunk(delta="当前项目 Agent 已收到请求，并会基于可用工具给出研究结论。", finish_reason="stop")


class ToolLimitFinalizingModelClient:
    def __init__(self) -> None:
        self.calls = 0
        self.final_tools_seen: list[Any] = []

    async def stream(self, **kwargs: Any):
        self.calls += 1
        if self.calls == 1:
            yield ModelStreamChunk(
                tool_call={
                    "id": "call-screening",
                    "name": "screening_run",
                    "arguments": {"sector": "储能"},
                },
                finish_reason="tool_calls",
            )
            return
        self.final_tools_seen.append(kwargs.get("tools"))
        yield ModelStreamChunk(
            delta="工具预算已用尽，基于已有结果给出最终结论：储能研究需要补充外部检索证据。",
            finish_reason="stop",
        )


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
async def test_agent_forces_final_answer_when_tool_iteration_limit_is_reached(fake_db):
    _ = fake_db
    principal = _principal(USER_A)
    session = await ResearchSessionService().create_session(
        principal, title="工具预算总结"
    )
    model_client = ToolLimitFinalizingModelClient()

    result = await ResearchAgentLoop(
        model_client=model_client,
        session_service=ResearchSessionService(),
        event_service=ResearchEventService(),
        max_tool_iterations=1,
    ).run(
        principal=principal,
        session_id=session["session_id"],
        user_message="分析储能板块",
        attempt_id="attempt-limit",
    )

    messages = await ResearchSessionService().list_messages(
        session["session_id"], USER_A["id"]
    )
    events = await ResearchEventService().list_after(
        session_id=session["session_id"], user_id=USER_A["id"], after_event_id=0
    )

    assert model_client.calls == 2
    assert model_client.final_tools_seen == [[]]
    assert "基于已有结果给出最终结论" in result["content"]
    assert "基于已有结果给出最终结论" in messages[-1]["content"]
    assert result["finish_reason"] == "tool_iteration_limit:stop"
    assert [event["event_type"] for event in events].count("message_completed") == 1


@pytest.mark.asyncio
async def test_agent_infers_backtest_arguments_from_user_request(fake_db, monkeypatch):
    async def fake_series(symbols: list[str], **_kwargs: Any) -> dict[str, dict[str, Any]]:
        return _sample_series(symbols)

    monkeypatch.setattr(quant_module, "load_price_series", fake_series)
    EmptyBacktestArgumentsModelClient.calls = 0
    principal = _principal(USER_A)
    session = await ResearchSessionService().create_session(
        principal, title="空参数回测"
    )

    result = await ResearchAgentLoop(
        model_client=EmptyBacktestArgumentsModelClient(principal),
        session_service=ResearchSessionService(),
        event_service=ResearchEventService(),
    ).run(
        principal=principal,
        session_id=session["session_id"],
        user_message=(
            "Create a risk-parity style backtest for symbols 000001.SZ, "
            "BTC-USDT, and AAPL from 2025-01-01 to 2026-06-01."
        ),
        attempt_id="attempt-empty-backtest",
    )

    events = await ResearchEventService().list_after(
        session_id=session["session_id"], user_id=USER_A["id"], after_event_id=0
    )
    started = [event for event in events if event["event_type"] == "tool_started"]
    completed = [event for event in events if event["event_type"] == "tool_completed"]

    assert result["finish_reason"] == "stop"
    assert started[0]["payload"]["arguments"]["symbols"] == ["000001.SZ", "BTC-USDT", "AAPL"]
    assert started[0]["payload"]["arguments"]["start_date"] == "2025-01-01"
    assert started[0]["payload"]["arguments"]["end_date"] == "2026-06-01"
    assert completed[0]["payload"]["result"]["status"] == "completed"


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
async def test_user_can_rename_and_delete_only_own_research_session(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="储能分析"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    renamed = await research_agent_router.update_research_session(
        session_id,
        research_agent_router.ResearchSessionUpdateRequest(title="储能复盘"),
        current_user=USER_A,
    )

    assert renamed["data"]["title"] == "储能复盘"
    with pytest.raises(HTTPException) as exc:
        await research_agent_router.update_research_session(
            session_id,
            research_agent_router.ResearchSessionUpdateRequest(title="越权改名"),
            current_user=USER_B,
        )
    assert exc.value.status_code == 404

    await ResearchSessionService().append_message(
        session_id=session_id,
        user_id=USER_A["id"],
        role="user",
        content="分析储能",
    )
    await ResearchEventService().append(
        session_id=session_id,
        user_id=USER_A["id"],
        event_type="tool_completed",
        payload={"tool_name": "alpha_bench"},
    )
    await ResearchArtifactService().create_artifact(
        session_id=session_id,
        user_id=USER_A["id"],
        artifact_type="research_report",
        payload={"summary": "ok"},
    )

    with pytest.raises(HTTPException) as exc:
        await research_agent_router.delete_research_session(
            session_id,
            current_user=USER_B,
        )
    assert exc.value.status_code == 404

    deleted = await research_agent_router.delete_research_session(
        session_id,
        current_user=USER_A,
    )

    assert deleted["data"]["status"] == "deleted"
    assert await ResearchSessionService().get_session(session_id, USER_A["id"]) is None
    assert (
        await ResearchSessionService().list_messages(session_id, USER_A["id"])
    ) == []
    assert (
        await ResearchEventService().list_after(
            session_id=session_id, user_id=USER_A["id"], after_event_id=0
        )
    ) == []
    assert fake_db.research_artifacts.documents == []


@pytest.mark.asyncio
async def test_user_prompt_route_runs_stock_workflow_from_provider_tool_calls(fake_db, monkeypatch):
    _ = fake_db
    FakeProviderModelClient.calls = 0
    monkeypatch.setattr(
        runtime_module, "OpenAICompatibleModelClient", FakeProviderModelClient
    )
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
        background_tasks=BackgroundTasks(),
        current_user=USER_A,
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    messages = await ResearchSessionService().list_messages(session_id, USER_A["id"])
    session = await ResearchSessionService().get_session(session_id, USER_A["id"])
    event_types = [event["event_type"] for event in events]
    artifacts = fake_db.research_artifacts.documents

    assert response["success"] is True
    assert response["data"]["status"] == "queued"
    assert response["data"]["job_id"]
    assert response["data"]["attempt_id"]
    assert response["data"]["message_id"]
    assert messages[0]["role"] == "user"
    assert messages[0]["linked_attempt_id"] == response["data"]["attempt_id"]
    assert session["last_attempt_id"] == response["data"]["attempt_id"]
    assert "tool_completed" not in event_types
    assert artifacts == []

    await research_agent_router.runtime_service.run_queued_user_prompt(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session_id),
        session_id=session_id,
        user_message="分析 A 股储能板块，给出推荐个股",
        job_id=response["data"]["job_id"],
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    event_types = [event["event_type"] for event in events]
    tool_names = [
        event["payload"].get("tool_name")
        for event in events
        if event["event_type"] == "tool_completed"
    ]
    messages = await ResearchSessionService().list_messages(session_id, USER_A["id"])
    assistant_messages = [message for message in messages if message["role"] == "assistant"]

    assert "tool_completed" in event_types
    assert "message_completed" in event_types
    assert "task_completed" in event_types
    assert "screening_run" in tool_names
    assert "single_stock_analysis" in tool_names
    assert "report_write" not in tool_names
    assert assistant_messages[-1]["linked_attempt_id"] == response["data"]["attempt_id"]
    assert FakeProviderModelClient.calls == 3
    assert messages[-1]["content"] == "基于工具证据，储能板块优先关注 300750.SZ。"
    assert artifacts == []


@pytest.mark.asyncio
async def test_connector_prompt_uses_migrated_live_tool_without_fake_stock_workflow(fake_db, monkeypatch):
    _ = fake_db
    ConnectorProviderModelClient.calls = 0
    monkeypatch.setattr(runtime_module, "OpenAICompatibleModelClient", ConnectorProviderModelClient)
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="交易连接器检查"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    response = await research_agent_router.append_research_message(
        session_id,
        research_agent_router.ResearchMessageCreateRequest(
            role="user", content="检查交易连接器运行状态"
        ),
        background_tasks=BackgroundTasks(),
        current_user=USER_A,
    )

    await research_agent_router.runtime_service.run_queued_user_prompt(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session_id),
        session_id=session_id,
        user_message="检查交易连接器运行状态",
        job_id=response["data"]["job_id"],
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    messages = await ResearchSessionService().list_messages(session_id, USER_A["id"])

    event_types = [event["event_type"] for event in events]
    tool_names = [event["payload"].get("tool_name") for event in events]
    assert "attempt.created" in event_types
    assert "job_queued" in event_types
    assert "job_running" in event_types
    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    assert "assistant_delta" in event_types
    assert "message_completed" in event_types
    assert "task_completed" in event_types
    assert fake_db.research_artifacts.documents == []
    assert "trading_check" in tool_names
    assert "不会再伪造运行结果" not in messages[-1]["content"]
    assert "只读研究模式" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_cross_market_backtest_prompt_runs_real_agent_loop(fake_db, monkeypatch):
    _ = fake_db
    RiskParityProviderModelClient.calls = 0
    monkeypatch.setattr(
        runtime_module, "OpenAICompatibleModelClient", RiskParityProviderModelClient
    )
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="跨市场回测"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]
    prompt = (
        "Backtest a risk-parity portfolio of 000001.SZ, BTC-USDT, and AAPL "
        "for full-year 2024, compare against equal-weight baseline"
    )

    response = await research_agent_router.append_research_message(
        session_id,
        research_agent_router.ResearchMessageCreateRequest(role="user", content=prompt),
        background_tasks=BackgroundTasks(),
        current_user=USER_A,
    )

    await research_agent_router.runtime_service.run_queued_user_prompt(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session_id),
        session_id=session_id,
        user_message=prompt,
        job_id=response["data"]["job_id"],
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    messages = await ResearchSessionService().list_messages(session_id, USER_A["id"])
    tool_names = [
        event["payload"].get("tool_name")
        for event in events
        if event["event_type"] == "tool_completed"
    ]

    assert "backtest" in tool_names
    assert fake_db.research_artifacts.documents
    assert "不会再伪造运行结果" not in messages[-1]["content"]
    assert messages[-1]["content"] == "跨市场风险平价风格回测已完成，结果基于工具输出，不使用占位结论。"


@pytest.mark.asyncio
async def test_goal_mode_stock_prompt_runs_real_agent_loop(fake_db, monkeypatch):
    _ = fake_db
    monkeypatch.setattr(runtime_module, "OpenAICompatibleModelClient", TextOnlyProviderModelClient)
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="储能目标"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]
    goal_prompt = "\n".join(
        [
            "Start working on this research goal now.",
            "Keep it research-only, use available tools when evidence is needed, add concrete evidence to the goal ledger, and keep going until the goal is complete, blocked, waiting for user input, or budget-limited.",
            "",
            "Goal: 帮我分析 A 股的储能板块",
        ]
    )

    response = await research_agent_router.append_research_message(
        session_id,
        research_agent_router.ResearchMessageCreateRequest(
            role="user", content=goal_prompt
        ),
        background_tasks=BackgroundTasks(),
        current_user=USER_A,
    )

    result = await research_agent_router.runtime_service.run_queued_user_prompt(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session_id),
        session_id=session_id,
        user_message=goal_prompt,
        job_id=response["data"]["job_id"],
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    event_types = [event["event_type"] for event in events]
    tool_names = [
        event["payload"].get("tool_name")
        for event in events
        if event["event_type"] == "tool_completed"
    ]

    assert tool_names == []
    assert result["status"] == "completed"
    assert "job_completed" in event_types
    assert "attempt.completed" in event_types
    assert "task_failed" not in event_types


@pytest.mark.asyncio
async def test_general_chat_prompt_does_not_run_stock_research_pipeline(fake_db, monkeypatch):
    _ = fake_db
    monkeypatch.setattr(runtime_module, "OpenAICompatibleModelClient", TextOnlyProviderModelClient)
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="能力介绍"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    response = await research_agent_router.append_research_message(
        session_id,
        research_agent_router.ResearchMessageCreateRequest(
            role="user", content="用一句话说明你能做什么"
        ),
        background_tasks=BackgroundTasks(),
        current_user=USER_A,
    )

    result = await research_agent_router.runtime_service.run_queued_user_prompt(
        principal=ResearchPrincipal.from_user(USER_A, session_id=session_id),
        session_id=session_id,
        user_message="用一句话说明你能做什么",
        job_id=response["data"]["job_id"],
    )

    events = await ResearchEventService().list_after(
        session_id=session_id, user_id=USER_A["id"], after_event_id=0
    )
    messages = await ResearchSessionService().list_messages(session_id, USER_A["id"])
    event_types = [event["event_type"] for event in events]

    assert all(event["event_type"] != "tool_started" for event in events)
    assert all(event["event_type"] != "tool_completed" for event in events)
    assert result["status"] == "completed"
    assert "job_completed" in event_types
    assert "attempt.completed" in event_types
    assert "task_failed" not in event_types
    assert fake_db.research_artifacts.documents == []
    assert messages[-1]["role"] == "assistant"
