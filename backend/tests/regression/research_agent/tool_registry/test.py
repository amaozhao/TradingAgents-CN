from __future__ import annotations

import pytest

from app.services.research_agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research_agent.registry import ResearchToolRegistry


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
    }.issubset(names)
    assert "admin_config_write" not in names


def test_default_registry_exposes_admin_tools_to_admin_user():
    tools = ResearchToolRegistry.default().for_principal(_principal(is_admin=True))
    names = {tool.name for tool in tools}

    assert "admin_config_write" in names


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
