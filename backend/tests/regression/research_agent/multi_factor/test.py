from __future__ import annotations

import pytest

from app.services.research_agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research_agent.registry import ResearchToolRegistry
from app.services.research_agent.tools import multi_factor as multi_factor_module


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER, session_id="session-mf"),
        session_id="session-mf",
    )


@pytest.mark.asyncio
async def test_multi_factor_alpha_backtest_degrades_when_baostock_login_fails(monkeypatch):
    monkeypatch.setattr(
        multi_factor_module,
        "_load_hs300_constituents",
        lambda _limit: (["600519", "000001", "300750"], 300, "test.constituents"),
    )

    def fail_history(*_args, **_kwargs):
        raise RuntimeError("baostock login failed: 网络接收错误。")

    monkeypatch.setattr(multi_factor_module, "_load_baostock_history", fail_history)

    result = await ResearchToolRegistry.default().get("multi_factor_alpha_backtest").run(
        _context(),
        {
            "universe": "hs300",
            "factors": ["momentum", "reversal"],
            "sample_size": 10,
        },
    )

    assert result["status"] == "degraded"
    assert result["accepted"] is False
    assert result["source_diagnostics"]["history"] == "baostock login failed: 网络接收错误。"
