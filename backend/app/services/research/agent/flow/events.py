from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.research.agent.stage import stock_stage_title

from .graph import StockDagParityPlan

STOCK_WORKFLOW_STAGE_ORDER = [
    "validate_input",
    "prepare_state",
    "market_analysis",
    "sentiment_analysis",
    "news_analysis",
    "fundamentals_analysis",
    "research_debate",
    "research_manager",
    "trader_decision",
    "risk_debate",
    "final_risk_decision",
    "report_generation",
    "agent_summary",
]

ANALYST_STAGE_BY_KEY = {
    "market": "market_analysis",
    "social": "sentiment_analysis",
    "news": "news_analysis",
    "fundamentals": "fundamentals_analysis",
}

ANALYST_REPORT_BY_STAGE = {
    "market_analysis": "market_report",
    "sentiment_analysis": "sentiment_report",
    "news_analysis": "news_report",
    "fundamentals_analysis": "fundamentals_report",
}

NODE_STAGE = {
    "Market Analyst": "market_analysis",
    "tools_market": "market_analysis",
    "Msg Clear Market": "market_analysis",
    "Sentiment Analyst": "sentiment_analysis",
    "tools_social": "sentiment_analysis",
    "Msg Clear Social": "sentiment_analysis",
    "News Analyst": "news_analysis",
    "tools_news": "news_analysis",
    "Msg Clear News": "news_analysis",
    "Fundamentals Analyst": "fundamentals_analysis",
    "tools_fundamentals": "fundamentals_analysis",
    "Msg Clear Fundamentals": "fundamentals_analysis",
    "Bull Researcher": "research_debate",
    "Bear Researcher": "research_debate",
    "Research Manager": "research_manager",
    "Trader": "trader_decision",
    "Risky Analyst": "risk_debate",
    "Safe Analyst": "risk_debate",
    "Neutral Analyst": "risk_debate",
    "Risk Judge": "final_risk_decision",
    "Portfolio Manager": "final_risk_decision",
    "END": "agent_summary",
}


class StockWorkflowEventEmitter:
    def __init__(self, *, task_id: str, analysis_id: str, attempt_id: str | None):
        self.task_id = task_id
        self.analysis_id = analysis_id
        self.attempt_id = attempt_id
        self.events: list[dict[str, Any]] = []

    def node_event(
        self,
        *,
        node: str,
        status: str,
        edge_from: str | None = None,
        edge_to: str | None = None,
        report_keys_added: list[str] | None = None,
        message: str = "",
    ) -> dict[str, Any]:
        event = {
            "event_type": "stock_analysis.node",
            "node": node,
            "stage": NODE_STAGE.get(node, "agent_summary"),
            "status": status,
            "edge_from": edge_from,
            "edge_to": edge_to,
            "task_id": self.task_id,
            "analysis_id": self.analysis_id,
            "attempt_id": self.attempt_id,
            "report_keys_added": list(report_keys_added or []),
            "message": message,
            "created_at": _now_iso(),
        }
        self.events.append(event)
        return event


def build_stock_workflow_stage_events(
    *,
    plan: StockDagParityPlan,
    reports: dict[str, Any],
    task_id: str,
    analysis_id: str,
    attempt_id: str | None,
) -> list[dict[str, Any]]:
    selected_stage_by_key = {
        spec.key: ANALYST_STAGE_BY_KEY[spec.key] for spec in plan.analyst_specs
    }
    skipped = _skipped_stage_reasons(plan, selected_stage_by_key)
    completed = _completed_stages(reports)

    events = []
    for stage in STOCK_WORKFLOW_STAGE_ORDER:
        status = "completed"
        message = _completed_message(stage)
        if stage in skipped:
            status = "skipped"
            message = skipped[stage]
        elif stage not in completed:
            status = "pending"
            message = "等待工作流执行该阶段。"
        events.append(
            {
                "event_type": "stock_analysis.stage",
                "stage": stage,
                "title": stock_stage_title(stage),
                "status": status,
                "message": message,
                "task_id": task_id,
                "analysis_id": analysis_id,
                "attempt_id": attempt_id,
                "created_at": _now_iso(),
            }
        )
    return events


def _skipped_stage_reasons(
    plan: StockDagParityPlan,
    selected_stage_by_key: dict[str, str],
) -> dict[str, str]:
    skipped: dict[str, str] = {}
    for key, stage in ANALYST_STAGE_BY_KEY.items():
        if key not in selected_stage_by_key:
            skipped[stage] = "未选择该分析师。"

    for stage, status in plan.stage_status_overrides.items():
        if status == "skipped":
            skipped[stage] = (
                "用户关闭风险评估。"
                if stage in {"risk_debate", "final_risk_decision"}
                else "该阶段已跳过。"
            )
    return skipped


def _completed_stages(reports: dict[str, Any]) -> set[str]:
    completed = {"validate_input", "prepare_state"}
    for stage, report_key in ANALYST_REPORT_BY_STAGE.items():
        if reports.get(report_key):
            completed.add(stage)
    if reports.get("bull_researcher") or reports.get("bear_researcher"):
        completed.add("research_debate")
    if reports.get("research_team_decision") or reports.get("investment_plan"):
        completed.add("research_manager")
    if reports.get("trader_investment_plan"):
        completed.add("trader_decision")
    if (
        reports.get("risky_analyst")
        or reports.get("safe_analyst")
        or reports.get("neutral_analyst")
    ):
        completed.add("risk_debate")
    if reports.get("risk_management_decision"):
        completed.add("final_risk_decision")
    if reports:
        completed.update({"report_generation", "agent_summary"})
    return completed


def _completed_message(stage: str) -> str:
    return f"{stock_stage_title(stage)}已完成。"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
