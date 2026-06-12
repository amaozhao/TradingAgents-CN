from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.services.research.agent import artifacts as artifacts_module
from app.services.research.agent import events as events_module
from app.services.research.agent import goals as goals_module
from app.services.research.agent import jobs as jobs_module
from app.services.research.agent import live as live_module
from app.services.research.agent import memory as memory_module
from app.services.research.agent import sessions as sessions_module
from app.services.research.agent import stock as stock_module
from app.services.research.agent import swarm as swarm_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.loop import ModelStreamChunk
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.sessions import ResearchSessionService
from app.services.research.agent.tools import correlation as correlation_module
from app.services.research.agent.tools import files as files_module
from app.services.research.agent.tools import multi as _multi_package
from app.services.research.agent.tools.market import data as market_data_module
from app.services.research.agent.tools.multi import factor as multi_factor_module


USER = {"id": "user-tool-calls", "username": "tool-user", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not (value is not None and value > expected["$gt"]):
                return False
            if "$gte" in expected and not (value is not None and value >= expected["$gte"]):
                return False
            if "$lt" in expected and not (value is not None and value < expected["$lt"]):
                return False
            if "$lte" in expected and not (value is not None and value <= expected["$lte"]):
                return False
            if "$in" in expected and value not in expected["$in"]:
                return False
            if "$ne" in expected and value == expected["$ne"]:
                return False
            continue
        if value != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = [dict(document) for document in documents]

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.documents = sorted(
            self.documents, key=lambda item: item.get(key, 0), reverse=reverse
        )
        return self

    def limit(self, count: int):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length: int | None = None):
        return self.documents if length is None else self.documents[:length]

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

    async def delete_one(self, query: dict[str, Any]):
        for index, document in enumerate(self.documents):
            if _matches_query(document, query):
                del self.documents[index]
                return type("FakeDeleteResult", (), {"deleted_count": 1})()
        return type("FakeDeleteResult", (), {"deleted_count": 0})()


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()
        self.research_jobs = FakeCollection()
        self.research_attempts = FakeCollection()
        self.research_goals = FakeCollection()
        self.research_agent_memory = FakeCollection()
        self.research_hypotheses = FakeCollection()
        self.research_live_state = FakeCollection()
        self.research_live_audit = FakeCollection()
        self.research_swarm_runs = FakeCollection()
        self.research_swarm_events = FakeCollection()
        self.analysis_reports = FakeCollection()


class FakeWorkerModelClient:
    def __init__(self, _principal: ResearchPrincipal):
        pass

    async def stream(self, **_kwargs: Any):
        yield ModelStreamChunk(delta="worker summary", finish_reason="stop")


class FakeAnalysisService:
    def __init__(self):
        self.status_by_task_id = {
            "task-600519": {
                "task_id": "task-600519",
                "user_id": USER["id"],
                "status": "completed",
                "progress": 100,
                "current_step_name": "报告生成",
                "message": "分析完成",
            }
        }

    async def create_analysis_task(self, _user_id: str, _request: Any):
        return {"task_id": "task-600519", "status": "pending"}

    async def get_task_status(self, task_id: str, user_id: str | None = None):
        status = self.status_by_task_id.get(task_id)
        if not status:
            return None
        if user_id and str(status.get("user_id")) != str(user_id):
            return None
        return dict(status)


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    db.analysis_reports.documents.append(
        {
            "task_id": "task-600519",
            "user_id": USER["id"],
            "analysis_id": "analysis-600519",
            "stock_symbol": "600519",
            "status": "completed",
            "summary": "覆盖测试报告",
            "recommendation": "持有",
            "reports": {"market_report": "市场报告"},
            "decision": {"action": "持有"},
        }
    )
    for module in (
        sessions_module,
        events_module,
        artifacts_module,
        jobs_module,
        goals_module,
        memory_module,
        live_module,
        swarm_module,
        stock_module,
    ):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    monkeypatch.setattr(swarm_module, "OpenAICompatibleModelClient", FakeWorkerModelClient)
    return db


@pytest.fixture()
def deterministic_external_boundaries(monkeypatch):
    async def fake_web_get(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> httpx.Response:
        _ = headers, timeout
        if "duckduckgo.com" in url:
            content = b"""
            <html>
              <a class="result__a" href="https://example.com/a">Alpha Result</a>
              <a class="result__snippet">First snippet</a>
              <a class="result__a" href="https://example.com/b">Beta Result</a>
              <a class="result__snippet">Second snippet</a>
            </html>
            """
        else:
            content = b"<html><title>Example</title><p>public page content</p></html>"
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", url),
        )

    async def fake_market_snapshot(symbol: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "market": "CN",
            "status": "completed",
            "basic_info": {"name": "Fixture Corp"},
            "quote": {"last": 12.3},
            "history": {"prices": _prices(symbol), "source": "fixture"},
        }

    async def fake_price_series(symbols: list[str], **_kwargs: Any) -> dict[str, dict[str, Any]]:
        return {
            symbol: {
                "symbol": symbol,
                "source": "fixture",
                "prices": _prices(symbol),
                "returns": [0.01, -0.005, 0.015],
                "status": "completed",
            }
            for symbol in symbols
        }

    def fake_multi_factor_result(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": "multi_factor_alpha_backtest",
            "status": "completed",
            "universe": payload.get("universe") or "hs300",
            "sampled_count": 10,
            "metrics": {"long_short": {"observations": 3}},
            "_artifact_payload": {"kind": "multi_factor_alpha_backtest"},
        }

    async def fake_native_workflow(_context, **kwargs: Any):
        return {
            "tool": kwargs["tool_name"],
            "mode": "single",
            "status": "completed",
            "accepted": True,
            "stage": "agent_summary",
            "wait_status": "completed",
            "progress": 100,
            "task_id": "task-600519",
            "symbol": kwargs["symbol"],
            "market_type": kwargs["market_type"],
            "summary": "覆盖测试报告",
            "recommendation": "持有",
            "links": {
                "task": "/tasks?task_id=task-600519",
                "report": "/reports/view/task-600519",
            },
            "task_url": "/tasks?task_id=task-600519",
            "report_url": "/reports/view/task-600519",
        }

    monkeypatch.setattr(files_module, "_web_get", fake_web_get)
    monkeypatch.setattr(market_data_module, "lookup_market_snapshot", fake_market_snapshot)
    monkeypatch.setattr(correlation_module, "load_price_series", fake_price_series)
    monkeypatch.setattr(multi_factor_module, "_build_multi_factor_alpha_result", fake_multi_factor_result)
    monkeypatch.setattr(stock_module, "get_simple_analysis_service", lambda: FakeAnalysisService())
    monkeypatch.setattr(stock_module, "run_native_stock_workflow", fake_native_workflow)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda _model: {"provider": "qwen", "backend_url": "https://example.test/v1", "api_key": "key"},
    )
    assert _multi_package


def _prices(symbol: str) -> list[dict[str, Any]]:
    return [
        {"date": "2024-01-01", "symbol": symbol, "close": 10.0},
        {"date": "2024-01-02", "symbol": symbol, "close": 10.2},
        {"date": "2024-01-03", "symbol": symbol, "close": 10.1},
        {"date": "2024-01-04", "symbol": symbol, "close": 10.5},
    ]


def _context(principal: ResearchPrincipal, session_id: str) -> ToolExecutionContext:
    return ToolExecutionContext(principal=principal, session_id=session_id)


async def _run_tool(
    registry: ResearchToolRegistry,
    context: ToolExecutionContext,
    called: set[str],
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    result = await registry.get(name).run(context, payload)
    called.add(name)
    assert isinstance(result, dict), name
    return result


@pytest.mark.asyncio
async def test_all_enabled_research_agent_tools_are_invokable(
    fake_db, deterministic_external_boundaries
):
    _ = fake_db, deterministic_external_boundaries
    principal = ResearchPrincipal.from_user(USER)
    session = await ResearchSessionService().create_session(principal, title="tool calls")
    session_id = session["session_id"]
    principal = ResearchPrincipal.from_user(USER, session_id=session_id)
    context = _context(principal, session_id)
    await ResearchSessionService().append_message(
        session_id=session_id,
        user_id=principal.user_id,
        role="user",
        content="tool coverage search target",
    )

    registry = ResearchToolRegistry.default()
    enabled_tool_names = {
        tool.name for tool in registry.for_principal(principal, include_disabled=False)
    }
    called: set[str] = set()

    assert len(enabled_tool_names) == 51
    assert "web_search" in enabled_tool_names
    assert "run_swarm" in enabled_tool_names
    assert "trading_place_order" not in enabled_tool_names

    await _run_tool(registry, context, called, "market_data_lookup", {"symbol": "600519", "limit": 4})
    await _run_tool(registry, context, called, "screening_run", {"query": "energy storage"})
    single_analysis = await _run_tool(
        registry,
        context,
        called,
        "single_stock_analysis",
        {"symbol": "600519", "wait_for_completion": False},
    )
    await _run_tool(
        registry,
        context,
        called,
        "stock_analysis",
        {"mode": "single", "symbol": "600519", "wait_for_completion": False},
    )
    await _run_tool(
        registry,
        context,
        called,
        "stock_analysis_status",
        {"task_id": single_analysis["task_id"]},
    )
    await _run_tool(
        registry,
        context,
        called,
        "stock_analysis_report",
        {"task_id": single_analysis["task_id"]},
    )
    await _run_tool(registry, context, called, "batch_stock_analysis", {"symbols": ["600519", "000001"]})
    await _run_tool(registry, context, called, "report_lookup", {"report_id": "report-1"})
    report = await _run_tool(
        registry,
        context,
        called,
        "report_write",
        {
            "title": "Fixture report",
            "sector": {"name": "storage", "summary": "demand improves"},
            "correlation": {"findings": ["pair diversification checked"]},
        },
    )

    alpha_list = await _run_tool(registry, context, called, "alpha_list", {})
    alpha_id = alpha_list["items"][0]["id"]
    await _run_tool(registry, context, called, "alpha_detail", {"alpha_id": alpha_id})
    alpha_bench = await _run_tool(
        registry, context, called, "alpha_bench", {"alpha_id": alpha_id, "symbols": ["600519"]}
    )
    await _run_tool(
        registry,
        context,
        called,
        "alpha_compare",
        {"alpha_ids": [alpha_id], "symbols": ["600519"]},
    )
    correlation = await _run_tool(
        registry,
        context,
        called,
        "correlation_matrix",
        {"symbols": ["600519", "000001"], "window": 4},
    )

    await _run_tool(registry, context, called, "compact_context", {"reason": "coverage"})
    await _run_tool(registry, context, called, "session_search", {"query": "coverage"})
    await _run_tool(registry, context, called, "check_background", {"job_id": alpha_bench["job_id"]})

    await _run_tool(registry, context, called, "factor_analysis", {"returns": [0.01, -0.02, 0.03]})
    backtest = await _run_tool(
        registry,
        context,
        called,
        "backtest",
        {"returns": [0.01, -0.02, 0.03], "signals": [1, 0.5, 1]},
    )
    await _run_tool(
        registry,
        context,
        called,
        "options_pricing",
        {"spot": 100, "strike": 105, "volatility": 0.2, "time_to_expiry": 0.5, "rate": 0.02},
    )
    await _run_tool(registry, context, called, "pattern", {"prices": [10, 11, 10.5, 12]})

    await _run_tool(registry, context, called, "read_file", {"text": "inline file", "filename": "file.txt"})
    await _run_tool(
        registry,
        context,
        called,
        "read_document",
        {"text": "inline document", "filename": "memo.md"},
    )
    await _run_tool(registry, context, called, "read_url", {"url": "https://example.com"})
    await _run_tool(registry, context, called, "web_search", {"query": "TradingAgents", "limit": 2})

    goal = await _run_tool(
        registry,
        context,
        called,
        "start_research_goal",
        {"title": "Coverage goal", "criteria": ["all tools called"]},
    )
    goal_id = goal["goal_id"]
    await _run_tool(registry, context, called, "get_research_goal", {})
    await _run_tool(
        registry,
        context,
        called,
        "add_goal_evidence",
        {"expected_goal_id": goal_id, "evidence": {"summary": "called tools"}},
    )
    await _run_tool(
        registry,
        context,
        called,
        "update_research_goal_status",
        {"expected_goal_id": goal_id, "status": "completed", "reason": "coverage"},
    )

    await _run_tool(registry, context, called, "load_skill", {"name": "web-reader"})
    await _run_tool(registry, context, called, "trading_connections", {})
    await _run_tool(registry, context, called, "trading_select_connection", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_check", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_account", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_positions", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_orders", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_quote", {"broker": "paper"})
    await _run_tool(registry, context, called, "trading_history", {"broker": "paper"})
    await _run_tool(
        registry,
        context,
        called,
        "propose_mandate_profiles",
        {"broker": "paper", "account_ref": "research-only"},
    )

    await _run_tool(
        registry,
        context,
        called,
        "run_swarm",
        {"preset": "quant_strategy_desk", "variables": {"topic": "coverage"}},
    )
    strategy = await _run_tool(
        registry,
        context,
        called,
        "extract_shadow_strategy",
        {"description": "buy strength and cap loss"},
    )
    shadow_backtest = await _run_tool(
        registry,
        context,
        called,
        "run_shadow_backtest",
        {"strategy_id": strategy["strategy_id"], "returns": [0.01, -0.02, 0.03]},
    )
    await _run_tool(
        registry,
        context,
        called,
        "render_shadow_report",
        {"strategy_id": strategy["strategy_id"], "backtest_id": shadow_backtest["backtest_id"], "summary": "ok"},
    )
    await _run_tool(
        registry,
        context,
        called,
        "scan_shadow_signals",
        {"signals": [{"symbol": "600519", "score": 0.8}]},
    )
    await _run_tool(
        registry,
        context,
        called,
        "analyze_trade_journal",
        {"text": "600519.SH profit 10\n000001.SZ loss 3 stop loss"},
    )
    await _run_tool(
        registry,
        context,
        called,
        "multi_factor_alpha_backtest",
        {"universe": "hs300", "factors": ["momentum"], "sample_size": 10},
    )

    await _run_tool(registry, context, called, "remember", {"content": "coverage memory"})
    hypothesis = await _run_tool(
        registry,
        context,
        called,
        "create_hypothesis",
        {"title": "Coverage hypothesis", "thesis": "all enabled tools remain callable"},
    )
    hypothesis_id = hypothesis["hypothesis"]["hypothesis_id"]
    await _run_tool(
        registry,
        context,
        called,
        "update_hypothesis",
        {"hypothesis_id": hypothesis_id, "status": "validated"},
    )
    await _run_tool(registry, context, called, "search_hypotheses", {"query": "Coverage"})
    await _run_tool(
        registry,
        context,
        called,
        "link_backtest",
        {"hypothesis_id": hypothesis_id, "backtest_id": backtest["artifact_id"]},
    )

    assert report["artifact_id"]
    assert correlation["status"] == "completed"
    assert called == enabled_tool_names


@pytest.mark.asyncio
async def test_enabled_research_agent_tools_handle_empty_agent_payloads(
    fake_db, deterministic_external_boundaries
):
    _ = fake_db, deterministic_external_boundaries
    principal = ResearchPrincipal.from_user(USER)
    session = await ResearchSessionService().create_session(
        principal, title="empty tool payloads"
    )
    session_id = session["session_id"]
    principal = ResearchPrincipal.from_user(USER, session_id=session_id)
    context = _context(principal, session_id)

    registry = ResearchToolRegistry.default()
    results: dict[str, dict[str, Any]] = {}
    for tool in registry.for_principal(principal, include_disabled=False):
        result = await tool.run(context, {})
        assert isinstance(result, dict), tool.name
        results[tool.name] = result

    assert len(results) == 51
    assert results["update_hypothesis"]["status"] == "config_required"
    assert results["update_hypothesis"]["missing"] == ["hypothesis_id"]
    assert results["link_backtest"]["status"] == "config_required"
    assert results["correlation_matrix"]["status"] == "config_required"
    assert results["extract_shadow_strategy"]["status"] == "config_required"
    assert {
        name: result
        for name, result in results.items()
        if result.get("status") == "error"
    } == {}


@pytest.mark.asyncio
async def test_web_get_uses_httpx_proxy_keyword(monkeypatch):
    calls: list[dict[str, Any]] = []

    class FakeAsyncClient:
        def __init__(self, **kwargs: Any):
            if "proxies" in kwargs:
                raise TypeError("AsyncClient.__init__() got an unexpected keyword argument 'proxies'")
            calls.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: Any):
            return None

        async def get(self, url: str, **_kwargs: Any):
            return httpx.Response(
                200,
                content=b"ok",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(files_module, "_web_proxy_candidates", lambda: ["http://127.0.0.1:7897"])
    monkeypatch.setattr(files_module.httpx, "AsyncClient", FakeAsyncClient)

    response = await files_module._web_get("https://example.com")

    assert response.text == "ok"
    assert calls == [
        {
            "timeout": 10.0,
            "follow_redirects": True,
            "trust_env": False,
            "proxy": "http://127.0.0.1:7897",
        }
    ]
