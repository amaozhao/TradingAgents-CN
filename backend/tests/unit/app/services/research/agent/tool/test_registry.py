from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import stock as stock_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry


def _principal(is_admin: bool = False) -> ResearchPrincipal:
    return ResearchPrincipal.from_user(
        {
            "id": "admin" if is_admin else "user-a",
            "is_admin": is_admin,
            "roles": ["admin"] if is_admin else [],
        },
        session_id="session-1",
    )


class FakeAnalysisService:
    async def create_analysis_task(self, _user_id: str, _request):
        return {"task_id": "task-600519", "status": "pending"}

    async def get_task_status(self, _task_id: str, user_id: str | None = None):
        return {"task_id": "task-600519", "user_id": user_id, "status": "queued"}


def test_default_registry_filters_tools_for_normal_user():
    principal = _principal()
    tools = ResearchToolRegistry.default().for_principal(principal)
    names = {tool.name for tool in tools}

    assert {
        "market_data_lookup",
        "screening_run",
        "stock_analysis",
        "single_stock_analysis",
        "batch_stock_analysis",
        "report_lookup",
        "report_write",
        "compact_context",
        "session_search",
        "check_background",
        "factor_analysis",
        "backtest",
        "multi_factor_alpha_backtest",
        "read_document",
        "read_url",
        "web_search",
        "start_research_goal",
        "load_skill",
        "trading_connections",
        "propose_mandate_profiles",
        "run_swarm",
        "extract_shadow_strategy",
        "analyze_trade_journal",
    }.issubset(names)
    assert "admin_config_write" not in names
    assert "bash" not in names
    assert "write_file" not in names
    assert "save_skill" not in names
    assert "trading_place_order" not in names
    assert "mcp_remote" not in names


def test_default_registry_exposes_admin_tools_to_admin_user():
    tools = ResearchToolRegistry.default().for_principal(_principal(is_admin=True))
    names = {tool.name for tool in tools}

    assert "admin_config_write" in names
    assert "bash" in names
    assert "write_file" in names
    assert "save_skill" in names
    assert "trading_place_order" in names


def test_default_registry_can_hide_disabled_placeholders_from_model_tools():
    tools = ResearchToolRegistry.default().for_principal(
        _principal(), include_disabled=False
    )
    names = {tool.name for tool in tools}

    assert "run_swarm" in names
    assert "market_data_lookup" in names
    assert "stock_analysis" in names
    assert "single_stock_analysis" in names
    assert "background_run" not in names
    assert all(tool.enabled for tool in tools)


def test_default_registry_tool_schemas_are_well_formed():
    tools = ResearchToolRegistry.default().all()

    assert tools
    assert len({tool.name for tool in tools}) == len(tools)

    for tool in tools:
        assert tool.name
        assert tool.description
        assert tool.permission
        assert tool.schema.get("type") == "object"

        properties = tool.schema.get("properties", {})
        assert isinstance(properties, dict)

        for field in tool.schema.get("required", []):
            assert field in properties

        for field_schema in properties.values():
            enum = field_schema.get("enum") if isinstance(field_schema, dict) else None
            if enum is not None:
                assert isinstance(enum, list)
                assert enum
                assert len(enum) == len(set(enum))


@pytest.mark.asyncio
async def test_tool_run_rejects_principal_without_required_permission():
    registry = ResearchToolRegistry.default()
    admin_tool = registry.get("admin_config_write")
    context = ToolExecutionContext(principal=_principal(), session_id="session-1")

    with pytest.raises(PermissionError):
        await admin_tool.run(context, {})


@pytest.mark.asyncio
async def test_tool_run_accepts_authorized_principal(monkeypatch):
    monkeypatch.setattr(
        stock_module, "get_simple_analysis_service", lambda: FakeAnalysisService()
    )

    async def fake_agent_workflow(_context, **kwargs: Any):
        return {
            "tool": kwargs["tool_name"],
            "mode": "single",
            "accepted": True,
            "status": "completed",
            "task_id": "task-600519",
            "symbol": kwargs["symbol"],
        }

    monkeypatch.setattr(stock_module, "run_agent_stock_workflow", fake_agent_workflow)

    async def fake_analysis_parameters(payload: dict[str, Any]):
        return (
            stock_module.AnalysisParameters(
                market_type=payload.get("market_type") or "A股",
                research_depth=payload.get("research_depth") or "标准",
                selected_analysts=payload.get("selected_analysts")
                or ["market", "fundamentals"],
                quick_analysis_model="quick",
                deep_analysis_model="deep",
            ),
            [],
            [],
        )

    async def no_missing_keys(_parameters) -> list[str]:
        return []

    monkeypatch.setattr(
        stock_module, "_analysis_parameters_async", fake_analysis_parameters
    )
    monkeypatch.setattr(stock_module, "_missing_model_keys_async", no_missing_keys)
    registry = ResearchToolRegistry.default()
    tool = registry.get("stock_analysis")
    context = ToolExecutionContext(principal=_principal(), session_id="session-1")

    result = await tool.run(
        context, {"mode": "single", "symbol": "600519", "wait_for_completion": False}
    )

    assert result["tool"] == "stock_analysis"
    assert result["mode"] == "single"
    assert result["accepted"] is True
    assert result["status"] == "completed"
    assert result["task_id"] == "task-600519"
    assert result["symbol"] == "600519"


@pytest.mark.asyncio
async def test_not_yet_migrated_tool_returns_explicit_disabled_state():
    registry = ResearchToolRegistry.default()
    tool = registry.get("background_run")
    context = ToolExecutionContext(principal=_principal(), session_id="session-1")

    result = await tool.run(context, {"task": "unsafe"})

    assert result["status"] == "disabled_config_required"
    assert result["accepted"] is False
    assert result["source_tool_class"] == "BackgroundRunTool"


@pytest.mark.asyncio
async def test_admin_unsafe_tool_is_registered_but_disabled():
    registry = ResearchToolRegistry.default()
    tool = registry.get("bash")
    context = ToolExecutionContext(
        principal=_principal(is_admin=True), session_id="session-1"
    )

    result = await tool.run(context, {"cmd": "pwd"})

    assert result["status"] == "disabled_config_required"
    assert result["accepted"] is False
    assert result["required_capability"] == "sandboxed_shell"
