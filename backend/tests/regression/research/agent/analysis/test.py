from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import stock as stock_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeAnalysisService:
    def __init__(self):
        self.created: list[tuple[str, Any]] = []
        self.status_by_task_id: dict[str, dict[str, Any]] = {}
        self.status_sequence_by_task_id: dict[str, list[dict[str, Any]]] = {}

    async def create_analysis_task(self, user_id: str, request):
        self.created.append((user_id, request))
        return {
            "task_id": "task-600519",
            "status": "pending",
            "message": "任务已创建，等待执行",
        }

    async def get_task_status(self, task_id: str, user_id: str | None = None):
        sequence = self.status_sequence_by_task_id.get(task_id)
        if sequence:
            status = sequence.pop(0)
            if not sequence:
                self.status_by_task_id[task_id] = status
        else:
            status = self.status_by_task_id.get(task_id)
        if not status:
            return None
        if user_id and str(status.get("user_id")) != str(user_id):
            return None
        return dict(status)


class FakeQueueService:
    def __init__(self):
        self.enqueued: list[dict[str, Any]] = []

    async def enqueue_task(self, **kwargs):
        self.enqueued.append(kwargs)
        return kwargs["task_id"]


class FakeReportCollection:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents
        self.last_query: dict[str, Any] | None = None

    async def find_one(self, query: dict[str, Any]):
        self.last_query = query
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None


class FakeDb:
    def __init__(self, reports: list[dict[str, Any]]):
        self.analysis_reports = FakeReportCollection(reports)


def _context() -> ToolExecutionContext:
    principal = ResearchPrincipal.from_user(USER, session_id="session-1")
    return ToolExecutionContext(principal=principal, session_id="session-1")


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_submits_existing_dag_task(monkeypatch):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("single_stock_analysis")
    result = await tool.run(
        _context(),
        {
            "symbol": "600519",
            "market_type": "A股",
            "analysis_date": "2026-06-11",
            "research_depth": "标准",
            "selected_analysts": ["market", "fundamentals", "news"],
            "include_sentiment": False,
            "include_risk": True,
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-max",
            "wait_for_completion": False,
        },
    )

    assert result["tool"] == "single_stock_analysis"
    assert result["accepted"] is True
    assert result["status"] == "queued"
    assert result["stage"] == "analysis_task"
    assert result["wait_status"] == "not_waited"
    assert result["task_id"] == "task-600519"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }
    assert result["task_url"] == "/tasks?task_id=task-600519"
    assert result["report_url"] == "/reports/view/task-600519"

    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.get_symbol() == "600519"
    assert request.parameters.market_type == "A股"
    assert request.parameters.research_depth == "标准"
    assert request.parameters.selected_analysts == ["market", "fundamentals", "news"]
    assert request.parameters.include_sentiment is False

    [queued] = queue.enqueued
    assert queued["user_id"] == "user-a"
    assert queued["symbol"] == "600519"
    assert queued["task_id"] == "task-600519"
    assert queued["params"]["task_id"] == "task-600519"
    assert queued["params"]["selected_analysts"] == ["market", "fundamentals", "news"]


@pytest.mark.asyncio
async def test_stock_analysis_tool_submits_single_mode_through_same_queue_adapter(
    monkeypatch,
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("stock_analysis")
    result = await tool.run(
        _context(),
        {
            "mode": "single",
            "symbol": "600519",
            "market_type": "A股",
            "research_depth": "标准",
            "selected_analysts": ["market", "fundamentals"],
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-max",
            "wait_for_completion": False,
        },
    )

    assert result["tool"] == "stock_analysis"
    assert result["mode"] == "single"
    assert result["accepted"] is True
    assert result["status"] == "queued"
    assert result["task_id"] == "task-600519"
    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.get_symbol() == "600519"
    assert request.parameters.selected_analysts == ["market", "fundamentals"]
    [queued] = queue.enqueued
    assert queued["task_id"] == "task-600519"
    assert queued["params"]["symbol"] == "600519"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_symbol", "market_type", "expected_symbol", "expected_market"),
    [
        ("600519", "A股", "600519", "A股"),
        ("0700.HK", None, "0700", "港股"),
        ("AAPL", None, "AAPL", "美股"),
    ],
)
async def test_stock_analysis_baseline_fixture_inputs_are_structurally_compatible(
    monkeypatch, raw_symbol, market_type, expected_symbol, expected_market
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis")
        .run(
            _context(),
            {
                "mode": "single",
                "symbol": raw_symbol,
                "market_type": market_type,
                "research_depth": "标准",
                "selected_analysts": ["market"],
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max",
                "wait_for_completion": False,
            },
        )
    )

    assert {
        "tool",
        "mode",
        "status",
        "accepted",
        "task_id",
        "symbol",
        "market_type",
        "task_url",
        "report_url",
    }.issubset(result)
    assert result["tool"] == "stock_analysis"
    assert result["mode"] == "single"
    assert result["symbol"] == expected_symbol
    assert result["market_type"] == expected_market
    [queued] = queue.enqueued
    assert queued["symbol"] == expected_symbol
    assert queued["params"]["market_type"] == expected_market


@pytest.mark.asyncio
async def test_stock_analysis_matches_existing_single_stock_queue_baseline(
    monkeypatch,
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    payload = {
        "mode": "single",
        "symbol": "600519.SH",
        "market_type": "A股",
        "analysis_date": "2026-06-11",
        "research_depth": "深度",
        "selected_analysts": ["market", "fundamentals", "news"],
        "include_sentiment": False,
        "include_risk": True,
        "quick_analysis_model": "qwen-turbo",
        "deep_analysis_model": "qwen-max",
        "wait_for_completion": False,
    }
    registry = ResearchToolRegistry.default()

    stock_result = await registry.get("stock_analysis").run(_context(), payload)
    baseline_result = await registry.get("single_stock_analysis").run(
        _context(), payload
    )

    assert stock_result["tool"] == "stock_analysis"
    assert baseline_result["tool"] == "single_stock_analysis"
    comparable_result_keys = {
        "mode",
        "status",
        "accepted",
        "task_id",
        "symbol",
        "market_type",
        "analysis_date",
        "research_depth",
        "selected_analysts",
        "include_sentiment",
        "include_risk",
        "task_url",
        "report_url",
        "message",
    }
    assert {key: stock_result[key] for key in comparable_result_keys} == {
        key: baseline_result[key] for key in comparable_result_keys
    }
    assert len(queue.enqueued) == 2
    assert queue.enqueued[0] == queue.enqueued[1]
    first_request = service.created[0][1]
    second_request = service.created[1][1]
    assert first_request.model_dump(mode="json") == second_request.model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_uses_configured_models_when_agent_omits_models(
    monkeypatch,
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "_load_active_system_config_doc",
        lambda: {
            "system_settings": {
                "quick_analysis_model": "minimax-m1",
                "deep_analysis_model": "minimax-m1",
            },
            "llm_configs": [
                {
                    "model_name": "minimax-m1",
                    "provider": "minimax",
                    "enabled": True,
                    "api_key": "minimax-key",
                    "priority": 10,
                    "capability_level": 4,
                    "suitable_roles": ["both"],
                    "features": ["tool_calling", "reasoning"],
                    "recommended_depths": ["标准", "深度", "全面"],
                }
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "minimax" if model == "minimax-m1" else "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "minimax-key" if model == "minimax-m1" else "",
        },
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("single_stock_analysis")
    result = await tool.run(
        _context(),
        {
            "symbol": "601818",
            "market_type": "A股",
            "research_depth": "标准",
            "selected_analysts": ["market", "fundamentals"],
            "wait_for_completion": False,
        },
    )

    assert result["accepted"] is True
    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.parameters.quick_analysis_model == "minimax-m1"
    assert request.parameters.deep_analysis_model == "minimax-m1"
    [queued] = queue.enqueued
    assert queued["params"]["quick_analysis_model"] == "minimax-m1"
    assert queued["params"]["deep_analysis_model"] == "minimax-m1"


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_uses_default_llm_when_quick_deep_are_unset(
    monkeypatch,
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "_load_active_system_config_doc",
        lambda: {
            "default_llm": "MiniMax-M3",
            "system_settings": {},
            "llm_configs": [
                {
                    "model_name": "glm-4",
                    "provider": "zhipu",
                    "enabled": True,
                    "api_key": "glm-key",
                    "suitable_roles": ["both"],
                },
                {
                    "model_name": "MiniMax-M3",
                    "provider": "minimax-token-plan",
                    "enabled": True,
                    "api_key": "minimax-key",
                    "suitable_roles": ["both"],
                },
            ],
        },
        raising=False,
    )
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "minimax-token-plan" if model == "MiniMax-M3" else "zhipu",
            "backend_url": "https://example.test/v1",
            "api_key": "minimax-key" if model == "MiniMax-M3" else "glm-key",
        },
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("single_stock_analysis")
    result = await tool.run(
        _context(),
        {"symbol": "601818", "research_depth": "标准", "wait_for_completion": False},
    )

    assert result["accepted"] is True
    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.parameters.quick_analysis_model == "MiniMax-M3"
    assert request.parameters.deep_analysis_model == "MiniMax-M3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_symbol", "expected_symbol", "expected_market"),
    [
        ("601989.SH", "601989", "A股"),
        ("SH601989", "601989", "A股"),
        ("sz000001", "000001", "A股"),
        ("000001.SZ", "000001", "A股"),
        ("0700.HK", "0700", "港股"),
        ("700", "700", "港股"),
        ("HK09988", "09988", "港股"),
        ("aapl", "AAPL", "美股"),
        ("AAPL.US", "AAPL", "美股"),
    ],
)
async def test_single_stock_analysis_tool_normalizes_exchange_symbol(
    monkeypatch, raw_symbol, expected_symbol, expected_market
):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("single_stock_analysis")
    result = await tool.run(
        _context(),
        {
            "symbol": raw_symbol,
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-max",
            "wait_for_completion": False,
        },
    )

    assert result["accepted"] is True
    assert result["symbol"] == expected_symbol
    assert result["market_type"] == expected_market
    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.get_symbol() == expected_symbol
    assert request.parameters.market_type == expected_market
    [queued] = queue.enqueued
    assert queued["symbol"] == expected_symbol
    assert queued["params"]["symbol"] == expected_symbol
    assert queued["params"]["stock_code"] == expected_symbol
    assert queued["params"]["market_type"] == expected_market


@pytest.mark.asyncio
async def test_stock_analysis_filters_social_analyst_for_a_share(monkeypatch):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis")
        .run(
            _context(),
            {
                "mode": "single",
                "symbol": "600519",
                "market_type": "A股",
                "selected_analysts": ["market", "social"],
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max",
                "wait_for_completion": False,
            },
        )
    )

    assert result["accepted"] is True
    assert result["selected_analysts"] == ["market"]
    assert {"stage": "social_analysis", "reason": "A 股默认禁用社媒分析。"} in result[
        "skipped_stages"
    ]
    [(user_id, request)] = service.created
    assert user_id == "user-a"
    assert request.parameters.selected_analysts == ["market"]
    [queued] = queue.enqueued
    assert queued["params"]["selected_analysts"] == ["market"]


@pytest.mark.asyncio
async def test_stock_analysis_returns_recoverable_stage_plan(monkeypatch):
    service = FakeAnalysisService()
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis")
        .run(
            _context(),
            {
                "mode": "single",
                "symbol": "600519",
                "market_type": "A股",
                "selected_analysts": ["market", "social"],
                "include_risk": False,
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max",
                "wait_for_completion": False,
            },
        )
    )

    plan_by_stage = {item["stage"]: item for item in result["stage_plan"]}
    assert [item["stage"] for item in result["stage_plan"]][:2] == [
        "validate_input",
        "prepare_data",
    ]
    assert plan_by_stage["validate_input"]["status"] == "pending"
    assert plan_by_stage["prepare_data"]["status"] == "pending"
    assert plan_by_stage["market_analysis"]["status"] == "pending"
    assert plan_by_stage["fundamentals_analysis"]["status"] == "skipped"
    assert plan_by_stage["fundamentals_analysis"]["reason"] == "未选择该分析师。"
    assert plan_by_stage["social_analysis"]["status"] == "skipped"
    assert plan_by_stage["social_analysis"]["reason"] == "A 股默认禁用社媒分析。"
    assert plan_by_stage["risk_review"]["status"] == "skipped"
    assert plan_by_stage["risk_review"]["reason"] == "用户关闭风险评估。"


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_waits_for_completed_report_by_default(
    monkeypatch,
):
    service = FakeAnalysisService()
    service.status_sequence_by_task_id["task-600519"] = [
        {
            "task_id": "task-600519",
            "user_id": "user-a",
            "status": "processing",
            "progress": 35,
            "message": "市场分析师正在分析",
        },
        {
            "task_id": "task-600519",
            "user_id": "user-a",
            "status": "completed",
            "progress": 100,
            "message": "分析完成",
        },
    ]
    queue = FakeQueueService()
    db = FakeDb(
        [
            {
                "task_id": "task-600519",
                "user_id": "user-a",
                "analysis_id": "analysis-1",
                "stock_symbol": "600519",
                "status": "completed",
                "summary": "贵州茅台基本面稳健。",
                "recommendation": "持有",
                "risk_level": "中",
                "key_points": ["现金流稳定"],
                "reports": {"market_report": "市场报告"},
                "decision": {"action": "持有"},
            }
        ]
    )
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(stock_module, "get_postgres_db", lambda: db, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )
    tool = ResearchToolRegistry.default().get("single_stock_analysis")
    result = await tool.run(
        _context(),
        {
            "symbol": "600519",
            "wait_timeout_seconds": 30,
            "poll_interval_seconds": 0.01,
        },
    )

    assert result["accepted"] is True
    assert result["status"] == "completed"
    assert result["stage"] == "agent_summary"
    assert result["wait_status"] == "completed"
    assert result["task_id"] == "task-600519"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }
    assert result["summary"] == "贵州茅台基本面稳健。"
    assert result["recommendation"] == "持有"
    assert result["report_summary"] == {
        "summary": "贵州茅台基本面稳健。",
        "recommendation": "持有",
        "risk_level": "中",
        "key_points": ["现金流稳定"],
    }
    assert result["report"]["analysis_id"] == "analysis-1"


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_returns_bounded_wait_timeout(monkeypatch):
    service = FakeAnalysisService()
    service.status_by_task_id["task-600519"] = {
        "task_id": "task-600519",
        "user_id": "user-a",
        "status": "processing",
        "progress": 42,
        "message": "市场分析师正在分析",
    }
    queue = FakeQueueService()
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        stock_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "key",
        },
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis")
        .run(
            _context(),
            {
                "mode": "single",
                "symbol": "600519",
                "quick_analysis_model": "qwen-turbo",
                "deep_analysis_model": "qwen-max",
                "wait_timeout_seconds": 0.001,
                "poll_interval_seconds": 0.001,
            },
        )
    )

    assert result["accepted"] is True
    assert result["status"] == "processing"
    assert result["stage"] == "wait_bounded"
    assert result["wait_status"] == "timed_out"
    assert result["wait_timed_out"] is True
    assert result["progress"] == 42
