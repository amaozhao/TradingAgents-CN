from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from app.services.research.agent.flow.stages.reports import (
    build_stock_workflow_report,
    build_stock_workflow_task_document,
    persist_stock_workflow_report,
    write_stock_workflow_report_files,
)


def _long(label: str) -> str:
    return f"{label} " + ("内容" * 20)


def _final_state() -> dict:
    return {
        "market_report": _long("market_report"),
        "sentiment_report": _long("sentiment_report"),
        "news_report": _long("news_report"),
        "fundamentals_report": _long("fundamentals_report"),
        "investment_plan": _long("investment_plan"),
        "trader_investment_plan": _long("trader_investment_plan"),
        "final_trade_decision": _long("final_trade_decision"),
        "investment_debate_state": {
            "bull_history": _long("bull_researcher"),
            "bear_history": _long("bear_researcher"),
            "judge_decision": _long("research_team_decision"),
        },
        "risk_debate_state": {
            "risky_history": _long("risky_analyst"),
            "safe_history": _long("safe_analyst"),
            "neutral_history": _long("neutral_analyst"),
            "judge_decision": _long("risk_management_decision"),
        },
        "performance_metrics": {"total_time": 12.5},
    }


def _context() -> SimpleNamespace:
    return SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        selected_analysts=["market", "social", "news", "fundamentals"],
        config={"research_depth": "标准"},
        task_id="task-1",
        principal=SimpleNamespace(user_id="user-1"),
    )


def _decision() -> dict:
    return {
        "action": "HOLD",
        "confidence": 0.81,
        "risk_score": 0.42,
        "target_price": "123.45",
        "reasoning": _long("reasoning"),
        "tokens_used": 321,
        "model_info": "FakeDeepLLM:fake-deep",
    }


def test_build_stock_workflow_report_matches_legacy_result_shape():
    result = build_stock_workflow_report(
        _context(),
        _final_state(),
        _decision(),
        execution_time=13.2,
    )

    assert set(result["reports"]) == {
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "investment_plan",
        "trader_investment_plan",
        "final_trade_decision",
        "bull_researcher",
        "bear_researcher",
        "research_team_decision",
        "risky_analyst",
        "safe_analyst",
        "neutral_analyst",
        "risk_management_decision",
    }
    for key in [
        "analysis_id",
        "stock_code",
        "stock_symbol",
        "analysis_date",
        "summary",
        "recommendation",
        "confidence_score",
        "risk_level",
        "key_points",
        "detailed_analysis",
        "execution_time",
        "tokens_used",
        "state",
        "analysts",
        "research_depth",
        "reports",
        "decision",
        "model_info",
        "performance_metrics",
    ]:
        assert key in result

    assert result["stock_code"] == "600519"
    assert result["stock_symbol"] == "600519"
    assert result["analysis_date"] == "2026-06-12"
    assert result["analysts"] == ["market", "social", "news", "fundamentals"]
    assert result["research_depth"] == "标准"
    assert result["execution_time"] == 13.2
    assert result["tokens_used"] == 321
    assert result["performance_metrics"] == {"total_time": 12.5}


@pytest.mark.asyncio
async def test_persist_stock_workflow_report_preserves_agent_source_and_owner():
    class FakeRepository:
        def __init__(self):
            self.report_doc = None
            self.task_update = None

        async def insert_report(self, document):
            self.report_doc = document
            return "inserted-1"

        async def update_task_result(self, task_id, result):
            self.task_update = (task_id, result)

    context = _context()
    result = build_stock_workflow_report(
        context,
        _final_state(),
        _decision(),
        execution_time=13.2,
    )
    repository = FakeRepository()

    report_doc = await persist_stock_workflow_report(
        context,
        result,
        repository=repository,
    )

    assert report_doc["source"] == "agent_workflow_dag_parity"
    assert report_doc["task_id"] == "task-1"
    assert report_doc["user_id"] == "user-1"
    assert report_doc["reports"]["final_trade_decision"] == result["state"][
        "final_trade_decision"
    ]
    assert repository.report_doc is report_doc
    assert repository.task_update == ("task-1", result)


def test_build_stock_workflow_task_document_marks_completed_task():
    context = _context()
    result = build_stock_workflow_report(
        context,
        _final_state(),
        _decision(),
        execution_time=13.2,
    )

    task_doc = build_stock_workflow_task_document(context, result)

    assert task_doc["task_id"] == "task-1"
    assert task_doc["user_id"] == "user-1"
    assert task_doc["status"] == "completed"
    assert task_doc["progress"] == 100
    assert task_doc["source"] == "agent_workflow_dag_parity"
    assert task_doc["analysis_id"] == result["analysis_id"]
    assert task_doc["result"]["analysis_id"] == result["analysis_id"]


def test_build_stock_workflow_task_document_serializes_langchain_messages():
    state = {
        **_final_state(),
        "messages": [HumanMessage(content="请分析 600519", id="message-1")],
    }
    result = build_stock_workflow_report(
        _context(),
        state,
        _decision(),
        execution_time=13.2,
    )

    task_doc = build_stock_workflow_task_document(_context(), result)

    json.dumps(task_doc["result"], ensure_ascii=False)
    assert task_doc["result"]["state"]["messages"] == [
        {"type": "human", "content": "请分析 600519", "id": "message-1"}
    ]


def test_write_stock_workflow_report_files_are_legacy_compatible(tmp_path: Path):
    context = _context()
    result = build_stock_workflow_report(
        context,
        _final_state(),
        _decision(),
        execution_time=13.2,
    )

    report_files = write_stock_workflow_report_files(
        context,
        result,
        output_dir=tmp_path,
    )

    assert set(report_files) >= {
        "market_report.md",
        "sentiment_report.md",
        "news_report.md",
        "fundamentals_report.md",
        "investment_plan.md",
        "trader_investment_plan.md",
        "final_trade_decision.md",
        "research_team_decision.md",
        "risk_management_decision.md",
        "analysis_metadata.json",
    }
    metadata = json.loads((tmp_path / "analysis_metadata.json").read_text())
    assert metadata["source"] == "agent_workflow_dag_parity"
    assert metadata["task_id"] == "task-1"
    assert metadata["stock_code"] == "600519"
    assert metadata["analysis_date"] == "2026-06-12"
