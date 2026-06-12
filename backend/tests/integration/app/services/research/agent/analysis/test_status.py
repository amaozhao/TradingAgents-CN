from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import stock as stock_module
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeAnalysisService:
    def __init__(self):
        self.status_by_task_id: dict[str, dict[str, Any]] = {}

    async def get_task_status(self, task_id: str, user_id: str | None = None):
        status = self.status_by_task_id.get(task_id)
        if not status:
            return None
        if user_id and str(status.get("user_id")) != str(user_id):
            return None
        return dict(status)


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
async def test_stock_analysis_status_reads_owner_scoped_task_status(monkeypatch):
    service = FakeAnalysisService()
    service.status_by_task_id["task-600519"] = {
        "task_id": "task-600519",
        "user_id": "user-a",
        "status": "running",
        "progress": 45,
        "current_step_name": "基本面分析师",
        "message": "基本面分析师正在分析",
    }
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )

    tool = ResearchToolRegistry.default().get("stock_analysis_status")
    result = await tool.run(_context(), {"task_id": "task-600519"})

    assert result["tool"] == "stock_analysis_status"
    assert result["accepted"] is True
    assert result["status"] == "running"
    assert result["progress"] == 45
    assert result["current_step"] == "基本面分析师"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }
    assert result["report_url"] == "/reports/view/task-600519"


@pytest.mark.asyncio
async def test_stock_analysis_status_returns_completed_report_link(monkeypatch):
    service = FakeAnalysisService()
    service.status_by_task_id["task-600519"] = {
        "task_id": "task-600519",
        "user_id": "user-a",
        "status": "completed",
        "progress": 100,
        "analysis_id": "analysis-1",
        "message": "分析完成",
    }
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_status")
        .run(_context(), {"task_id": "task-600519"})
    )

    assert result["accepted"] is True
    assert result["status"] == "completed"
    assert result["analysis_id"] == "analysis-1"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }


@pytest.mark.asyncio
async def test_stock_analysis_status_does_not_read_other_users_task(monkeypatch):
    service = FakeAnalysisService()
    service.status_by_task_id["task-600519"] = {
        "task_id": "task-600519",
        "user_id": "user-b",
        "status": "running",
        "progress": 45,
    }
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_status")
        .run(_context(), {"task_id": "task-600519"})
    )

    assert result["tool"] == "stock_analysis_status"
    assert result["accepted"] is False
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_stock_analysis_status_requires_task_id():
    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_status")
        .run(_context(), {})
    )

    assert result["tool"] == "stock_analysis_status"
    assert result["accepted"] is False
    assert result["status"] == "config_required"
    assert result["missing"] == ["task_id"]


@pytest.mark.asyncio
async def test_stock_analysis_report_reads_completed_owner_scoped_report(monkeypatch):
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
                "reports": {
                    "market_report": "市场报告",
                    "fundamentals_report": "基本面报告",
                },
                "decision": {"action": "持有", "confidence": 0.7},
            }
        ]
    )
    monkeypatch.setattr(stock_module, "get_postgres_db", lambda: db, raising=False)

    tool = ResearchToolRegistry.default().get("stock_analysis_report")
    result = await tool.run(_context(), {"task_id": "task-600519"})

    assert result["tool"] == "stock_analysis_report"
    assert result["accepted"] is True
    assert result["status"] == "completed"
    assert result["analysis_id"] == "analysis-1"
    assert result["links"] == {
        "task": "/tasks?task_id=task-600519",
        "report": "/reports/view/task-600519",
    }
    assert result["summary"] == "贵州茅台基本面稳健。"
    assert result["reports"]["fundamentals_report"] == "基本面报告"
    assert db.analysis_reports.last_query == {
        "task_id": "task-600519",
        "user_id": "user-a",
    }


@pytest.mark.asyncio
async def test_stock_analysis_report_refuses_processing_task_summary(monkeypatch):
    service = FakeAnalysisService()
    service.status_by_task_id["task-600519"] = {
        "task_id": "task-600519",
        "user_id": "user-a",
        "status": "processing",
        "progress": 40,
        "current_step_name": "市场分析师",
    }
    db = FakeDb(
        [
            {
                "task_id": "task-600519",
                "user_id": "user-a",
                "analysis_id": "analysis-1",
                "stock_symbol": "600519",
                "status": "completed",
                "summary": "这个摘要不应在 processing 状态返回。",
            }
        ]
    )
    monkeypatch.setattr(
        stock_module,
        "get_simple_analysis_service",
        lambda: service,
        raising=False,
    )
    monkeypatch.setattr(stock_module, "get_postgres_db", lambda: db, raising=False)

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_report")
        .run(_context(), {"task_id": "task-600519"})
    )

    assert result["accepted"] is False
    assert result["status"] == "processing"
    assert result["progress"] == 40
    assert result["current_step"] == "市场分析师"
    assert result["reason"] == "个股分析任务尚未完成，不能生成或返回最终报告摘要。"
    assert "summary" not in result
    assert db.analysis_reports.last_query is None


@pytest.mark.asyncio
async def test_stock_analysis_report_does_not_read_other_users_report(monkeypatch):
    db = FakeDb(
        [
            {
                "task_id": "task-600519",
                "user_id": "user-b",
                "analysis_id": "analysis-1",
                "status": "completed",
                "summary": "不应被读取。",
            }
        ]
    )
    monkeypatch.setattr(stock_module, "get_postgres_db", lambda: db, raising=False)

    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_report")
        .run(_context(), {"task_id": "task-600519"})
    )

    assert result["tool"] == "stock_analysis_report"
    assert result["accepted"] is False
    assert result["status"] == "not_found"
    assert db.analysis_reports.last_query == {
        "task_id": "task-600519",
        "user_id": "user-a",
    }


@pytest.mark.asyncio
async def test_stock_analysis_report_requires_task_id():
    result = (
        await ResearchToolRegistry.default()
        .get("stock_analysis_report")
        .run(_context(), {})
    )

    assert result["tool"] == "stock_analysis_report"
    assert result["accepted"] is False
    assert result["status"] == "config_required"
    assert result["missing"] == ["task_id"]
