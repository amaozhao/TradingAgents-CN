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


def _context() -> ToolExecutionContext:
    principal = ResearchPrincipal.from_user(USER, session_id="session-1")
    return ToolExecutionContext(principal=principal, session_id="session-1")


class WorkflowCalls(list[dict[str, Any]]):
    service: FakeAnalysisService


def _patch_native_workflow(monkeypatch):
    calls = WorkflowCalls()
    service = FakeAnalysisService()

    async def run_native_stock_workflow(
        context,
        *,
        tool_name: str,
        symbol: str,
        market_type: str,
        parameters,
        skipped_stages,
        stage_plan,
    ):
        calls.append(
            {
                "context": context,
                "symbol": symbol,
                "market_type": market_type,
                "parameters": parameters,
                "skipped_stages": skipped_stages,
                "stage_plan": stage_plan,
            }
        )
        return {
            "tool": tool_name,
            "mode": "single",
            "status": "completed",
            "accepted": True,
            "stage": "agent_summary",
            "wait_status": "completed",
            "progress": 100,
            "task_id": "task-600519",
            "analysis_id": "analysis-1",
            "symbol": symbol,
            "market_type": market_type,
            "analysis_date": parameters.analysis_date.isoformat()
            if parameters.analysis_date
            else None,
            "research_depth": parameters.research_depth,
            "selected_analysts": parameters.selected_analysts,
            "include_sentiment": parameters.include_sentiment,
            "include_risk": parameters.include_risk,
            "skipped_stages": skipped_stages,
            "stage_plan": stage_plan,
            "summary": "贵州茅台基本面稳健。",
            "recommendation": "持有",
            "risk_level": "中",
            "decision": {"action": "持有"},
            "report": {"analysis_id": "analysis-1"},
            "links": {
                "task": "/tasks?task_id=task-600519",
                "report": "/reports/view/task-600519",
            },
            "task_url": "/tasks?task_id=task-600519",
            "report_url": "/reports/view/task-600519",
            "message": "Agent-native 单股分析已完成，未提交原 LangGraph 队列。",
        }

    monkeypatch.setattr(stock_module, "get_simple_analysis_service", lambda: service)
    monkeypatch.setattr(
        stock_module,
        "run_native_stock_workflow",
        run_native_stock_workflow,
    )
    calls.service = service
    return calls


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_runs_native_workflow(monkeypatch):
    calls = _patch_native_workflow(monkeypatch)
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
    assert result["status"] == "completed"
    assert result["stage"] == "agent_summary"
    assert result["wait_status"] == "completed"
    assert result["task_id"] == "task-600519"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }
    assert result["task_url"] == "/tasks?task_id=task-600519"
    assert result["report_url"] == "/reports/view/task-600519"
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["symbol"] == "600519"
    assert call["market_type"] == "A股"
    assert call["parameters"].research_depth == "标准"
    assert call["parameters"].selected_analysts == ["market", "fundamentals", "news"]
    assert call["parameters"].include_sentiment is False


@pytest.mark.asyncio
async def test_stock_analysis_tool_runs_single_mode_through_native_workflow(
    monkeypatch,
):
    calls = _patch_native_workflow(monkeypatch)
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
    assert result["status"] == "completed"
    assert result["task_id"] == "task-600519"
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["symbol"] == "600519"
    assert call["parameters"].selected_analysts == ["market", "fundamentals"]


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
    calls = _patch_native_workflow(monkeypatch)
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
    [call] = calls
    assert call["symbol"] == expected_symbol
    assert call["market_type"] == expected_market


@pytest.mark.asyncio
async def test_stock_analysis_matches_single_stock_analysis_alias(
    monkeypatch,
):
    calls = _patch_native_workflow(monkeypatch)
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
    assert len(calls) == 2
    assert calls[0]["symbol"] == calls[1]["symbol"]
    assert calls[0]["parameters"].model_dump(mode="json") == calls[1][
        "parameters"
    ].model_dump(mode="json")


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_uses_configured_models_when_agent_omits_models(
    monkeypatch,
):
    calls = _patch_native_workflow(monkeypatch)
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
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["parameters"].quick_analysis_model == "minimax-m1"
    assert call["parameters"].deep_analysis_model == "minimax-m1"


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_uses_default_llm_when_quick_deep_are_unset(
    monkeypatch,
):
    calls = _patch_native_workflow(monkeypatch)
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
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["parameters"].quick_analysis_model == "MiniMax-M3"
    assert call["parameters"].deep_analysis_model == "MiniMax-M3"


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
    calls = _patch_native_workflow(monkeypatch)
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
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["symbol"] == expected_symbol
    assert call["parameters"].market_type == expected_market


@pytest.mark.asyncio
async def test_stock_analysis_filters_social_analyst_for_a_share(monkeypatch):
    calls = _patch_native_workflow(monkeypatch)
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
    [call] = calls
    assert call["context"].principal.user_id == "user-a"
    assert call["parameters"].selected_analysts == ["market"]


@pytest.mark.asyncio
async def test_stock_analysis_returns_recoverable_stage_plan(monkeypatch):
    _patch_native_workflow(monkeypatch)
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
    _patch_native_workflow(monkeypatch)
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
    assert result["report"]["analysis_id"] == "analysis-1"


@pytest.mark.asyncio
async def test_single_stock_analysis_tool_ignores_legacy_wait_timeout(monkeypatch):
    _patch_native_workflow(monkeypatch)
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
    assert result["status"] == "completed"
    assert result["stage"] == "agent_summary"
    assert result["wait_status"] == "completed"
    assert "wait_timed_out" not in result
    assert result["progress"] == 100
