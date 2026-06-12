from __future__ import annotations

import pytest

from app.services.research.agent import artifacts as artifacts_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args):
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
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(dict(document))

    def find(self, query):
        return FakeCursor([item for item in self.documents if all(item.get(key) == value for key, value in query.items())])


class FakeDb:
    def __init__(self):
        self.research_artifacts = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(artifacts_module, "get_postgres_db", lambda db=db: db)
    return db


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER, session_id="session-quant"),
        session_id="session-quant",
    )


@pytest.mark.asyncio
async def test_options_pricing_and_pattern_tools_require_caller_data():
    registry = ResearchToolRegistry.default()

    option = await registry.get("options_pricing").run(
        _context(),
        {
            "spot": 100,
            "strike": 100,
            "volatility": 0.2,
            "time_to_expiry": 1,
            "rate": 0.01,
            "option_type": "call",
        },
    )
    pattern = await registry.get("pattern").run(
        _context(), {"prices": [10, 11, 12, 13]}
    )
    missing_pattern = await registry.get("pattern").run(_context(), {"prices": [10]})

    assert option["status"] == "completed"
    assert option["price"] > 0
    assert pattern["pattern"]["trend"] == "uptrend"
    assert missing_pattern["status"] == "config_required"


@pytest.mark.asyncio
async def test_options_pricing_requires_complete_numeric_inputs():
    registry = ResearchToolRegistry.default()
    base_payload = {
        "spot": 100,
        "strike": 100,
        "volatility": 0.2,
        "time_to_expiry": 1,
        "option_type": "call",
    }

    for field in ("spot", "strike", "volatility", "time_to_expiry"):
        payload = dict(base_payload)
        payload.pop(field)
        missing_input = await registry.get("options_pricing").run(_context(), payload)

        assert missing_input["status"] == "config_required"
        assert missing_input["accepted"] is False
        assert field in missing_input["reason"]


@pytest.mark.asyncio
async def test_factor_analysis_and_backtest_use_caller_data(fake_db):
    registry = ResearchToolRegistry.default()

    factor = await registry.get("factor_analysis").run(
        _context(), {"returns": [0.01, -0.02, 0.03], "factor": "momentum"}
    )
    missing_factor = await registry.get("factor_analysis").run(_context(), {})
    backtest = await registry.get("backtest").run(
        _context(), {"returns": [0.01, -0.02, 0.03], "signals": [1, 0, 1]}
    )
    missing_backtest = await registry.get("backtest").run(_context(), {})

    assert factor["status"] == "completed"
    assert factor["artifact_id"]
    assert missing_factor["status"] == "config_required"
    assert backtest["status"] == "completed"
    assert backtest["artifact_id"]
    assert missing_backtest["status"] == "config_required"
    assert {item["artifact_type"] for item in fake_db.research_artifacts.documents} == {
        "factor_analysis",
        "backtest_run",
    }
