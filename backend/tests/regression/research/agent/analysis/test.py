from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.tools import analysis as analysis_tools_module


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeAnalysisService:
    def __init__(self):
        self.created: list[tuple[str, Any]] = []
        self.status_by_task_id: dict[str, dict[str, Any]] = {}

    async def create_analysis_task(self, user_id: str, request):
        self.created.append((user_id, request))
        return {"task_id": "task-600519", "status": "pending", "message": "任务已创建，等待执行"}

    async def get_task_status(self, task_id: str, user_id: str | None = None):
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
        analysis_tools_module, "get_simple_analysis_service", lambda: service, raising=False
    )
    monkeypatch.setattr(analysis_tools_module, "get_queue_service", lambda: queue, raising=False)
    monkeypatch.setattr(
        analysis_tools_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {"provider": "qwen", "backend_url": "https://example.test/v1", "api_key": "key"},
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
        },
    )

    assert result["tool"] == "single_stock_analysis"
    assert result["accepted"] is True
    assert result["status"] == "queued"
    assert result["task_id"] == "task-600519"
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
        analysis_tools_module, "get_simple_analysis_service", lambda: service, raising=False
    )

    tool = ResearchToolRegistry.default().get("stock_analysis_status")
    result = await tool.run(_context(), {"task_id": "task-600519"})

    assert result["tool"] == "stock_analysis_status"
    assert result["accepted"] is True
    assert result["status"] == "running"
    assert result["progress"] == 45
    assert result["current_step"] == "基本面分析师"


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
                "reports": {"market_report": "市场报告", "fundamentals_report": "基本面报告"},
                "decision": {"action": "持有", "confidence": 0.7},
            }
        ]
    )
    monkeypatch.setattr(analysis_tools_module, "get_postgres_db", lambda: db, raising=False)

    tool = ResearchToolRegistry.default().get("stock_analysis_report")
    result = await tool.run(_context(), {"task_id": "task-600519"})

    assert result["tool"] == "stock_analysis_report"
    assert result["accepted"] is True
    assert result["status"] == "completed"
    assert result["analysis_id"] == "analysis-1"
    assert result["summary"] == "贵州茅台基本面稳健。"
    assert result["reports"]["fundamentals_report"] == "基本面报告"
    assert db.analysis_reports.last_query == {"task_id": "task-600519", "user_id": "user-a"}
