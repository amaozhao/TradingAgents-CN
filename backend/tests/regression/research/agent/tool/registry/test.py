from __future__ import annotations

import pytest

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


def test_default_registry_filters_tools_for_normal_user():
    principal = _principal()
    tools = ResearchToolRegistry.default().for_principal(principal)
    names = {tool.name for tool in tools}

    assert {
        "market_data_lookup",
        "screening_run",
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


@pytest.mark.asyncio
async def test_tool_run_rejects_principal_without_required_permission():
    registry = ResearchToolRegistry.default()
    admin_tool = registry.get("admin_config_write")
    context = ToolExecutionContext(principal=_principal(), session_id="session-1")

    with pytest.raises(PermissionError):
        await admin_tool.run(context, {})


@pytest.mark.asyncio
async def test_tool_run_accepts_authorized_principal():
    registry = ResearchToolRegistry.default()
    tool = registry.get("single_stock_analysis")
    context = ToolExecutionContext(principal=_principal(), session_id="session-1")

    result = await tool.run(context, {"symbol": "600519"})

    assert result["tool"] == "single_stock_analysis"
    assert result["accepted"] is True
    assert result["payload"]["symbol"] == "600519"


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
    context = ToolExecutionContext(principal=_principal(is_admin=True), session_id="session-1")

    result = await tool.run(context, {"cmd": "pwd"})

    assert result["status"] == "disabled_config_required"
    assert result["accepted"] is False
    assert result["required_capability"] == "sandboxed_shell"
