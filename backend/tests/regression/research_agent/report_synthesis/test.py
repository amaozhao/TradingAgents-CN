from __future__ import annotations

from typing import Any

import pytest

from app.services.research_agent import artifacts as artifacts_module
from app.services.research_agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research_agent.tools.reports import report_tools


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeInsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self):
        self.documents: list[dict[str, Any]] = []

    async def insert_one(self, document: dict[str, Any]):
        self.documents.append(dict(document))
        return FakeInsertResult(str(document.get("_id")))

    async def find_one(self, query: dict[str, Any]):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None


class FakeDb:
    def __init__(self):
        self.research_artifacts = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(artifacts_module, "get_postgres_db", lambda: db)
    return db


def _context() -> ToolExecutionContext:
    return ToolExecutionContext(
        principal=ResearchPrincipal.from_user(USER_A, session_id="session-a"),
        session_id="session-a",
    )


def _report_write_tool():
    return next(tool for tool in report_tools() if tool.name == "report_write")


@pytest.mark.asyncio
async def test_report_write_persists_structured_recommendation_with_evidence(fake_db):
    result = await _report_write_tool().run(
        _context(),
        {
            "title": "储能板块研究报告",
            "sector": {
                "name": "储能",
                "summary": "储能需求受益于新能源装机和电网调峰需求。",
            },
            "universe": {
                "method": "screening_run",
                "symbols": ["300750.SZ", "002594.SZ"],
            },
            "screening_filters": {
                "industry": "储能",
                "market_cap_min": 50000000000,
                "roe_min": 10,
            },
            "correlation": {
                "artifact_id": "artifact-correlation-a",
                "findings": ["300750.SZ 与 002594.SZ 相关性低于组合阈值。"],
            },
            "alpha": {
                "artifact_id": "artifact-alpha-a",
                "findings": ["alpha101_001 对 300750.SZ 给出正向排序。"],
            },
            "single_stock_reports": [
                {
                    "symbol": "300750.SZ",
                    "report_id": "report-300750",
                    "task_id": "task-300750",
                    "summary": "盈利质量和产业链地位较强。",
                }
            ],
            "recommended_stocks": [
                {
                    "symbol": "300750.SZ",
                    "name": "宁德时代",
                    "reason": "Alpha、相关性和单股报告形成一致证据。",
                }
            ],
            "risk_factors": ["锂价波动可能压缩利润率。"],
            "data_limitations": ["新闻情绪样本覆盖最近 30 天。"],
            "artifact_ids": ["artifact-screening-a"],
            "task_ids": ["task-screening-a"],
        },
    )

    artifact = fake_db.research_artifacts.documents[0]
    report = artifact["payload"]
    sections = report["sections"]

    assert result["artifact_id"] == artifact["artifact_id"]
    assert artifact["artifact_type"] == "research_report"
    assert sections["sector_summary"]["sector"] == "储能"
    assert "新能源装机" in sections["sector_summary"]["summary"]
    assert sections["universe_construction"]["method"] == "screening_run"
    assert sections["universe_construction"]["symbols"] == ["300750.SZ", "002594.SZ"]
    assert sections["screening_filters"]["filters"]["roe_min"] == 10
    assert sections["correlation_findings"]["artifact_id"] == "artifact-correlation-a"
    assert "相关性" in sections["correlation_findings"]["findings"][0]
    assert sections["alpha_factor_findings"]["artifact_id"] == "artifact-alpha-a"
    assert "alpha101_001" in sections["alpha_factor_findings"]["findings"][0]
    assert sections["linked_single_stock_reports"]["reports"][0]["task_id"] == "task-300750"
    assert sections["recommended_stocks"]["items"][0]["symbol"] == "300750.SZ"
    assert sections["risk_factors"]["items"] == ["锂价波动可能压缩利润率。"]
    assert sections["data_limitations"]["items"] == ["新闻情绪样本覆盖最近 30 天。"]
    assert sections["linked_artifacts_and_tasks"]["artifact_ids"] == [
        "artifact-screening-a",
        "artifact-correlation-a",
        "artifact-alpha-a",
    ]
    assert sections["linked_artifacts_and_tasks"]["task_ids"] == [
        "task-screening-a",
        "task-300750",
    ]


@pytest.mark.asyncio
async def test_report_write_records_limitation_without_unsupported_recommendation(fake_db):
    result = await _report_write_tool().run(
        _context(),
        {
            "title": "储能板块研究报告",
            "sector": {"name": "储能", "summary": "缺少足够交叉验证证据。"},
            "universe": {"method": "manual", "symbols": ["300750.SZ"]},
            "recommended_stocks": [
                {"symbol": "300750.SZ", "reason": "仅用户指定，缺少证据。"}
            ],
        },
    )

    artifact = fake_db.research_artifacts.documents[0]
    sections = artifact["payload"]["sections"]

    assert result["artifact_id"] == artifact["artifact_id"]
    assert sections["recommended_stocks"]["items"] == []
    assert sections["recommended_stocks"]["limitation"]
    assert "证据不足" in sections["recommended_stocks"]["limitation"]
    assert any("证据不足" in item for item in sections["data_limitations"]["items"])
