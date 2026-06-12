from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StageStatus = Literal["pending", "running", "completed", "failed", "skipped"]


@dataclass(frozen=True)
class StockStagePlanItem:
    stage: str
    title: str
    status: StageStatus
    reason: str = ""

    def model_dump(self) -> dict[str, str]:
        payload = {
            "stage": self.stage,
            "title": self.title,
            "status": self.status,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


STOCK_STAGE_TITLES = {
    "validate_input": "参数校验",
    "prepare_state": "状态准备",
    "prepare_data": "数据准备",
    "market_analysis": "市场分析师",
    "sentiment_analysis": "情绪分析师",
    "fundamentals_analysis": "基本面分析师",
    "news_analysis": "新闻分析师",
    "social_analysis": "社媒分析师",
    "research_debate": "研究辩论",
    "research_manager": "研究经理",
    "trader_decision": "交易决策",
    "risk_debate": "风险辩论",
    "final_risk_decision": "最终风险决策",
    "risk_review": "风险评估",
    "report_generation": "报告生成",
    "wait_bounded": "等待窗口",
    "analysis_task": "单股分析任务",
    "agent_summary": "Agent 总结",
}

_ANALYST_STAGE_BY_ID = {
    "market": "market_analysis",
    "fundamentals": "fundamentals_analysis",
    "news": "news_analysis",
    "social": "social_analysis",
}

_WORKFLOW_STAGE_ORDER = [
    "validate_input",
    "prepare_data",
    "market_analysis",
    "fundamentals_analysis",
    "news_analysis",
    "social_analysis",
    "research_debate",
    "trader_decision",
    "risk_review",
    "report_generation",
    "agent_summary",
]


def stock_stage_title(stage: str) -> str:
    return STOCK_STAGE_TITLES.get(stage, "单股分析")


def planned_stock_stages(
    *,
    selected_analysts: list[str],
    include_risk: bool,
    initial_skipped: list[dict[str, str]],
) -> list[dict[str, str]]:
    skipped_by_stage = {
        item["stage"]: item.get("reason", "该阶段已跳过。")
        for item in initial_skipped
        if item.get("stage")
    }
    for analyst, stage in _ANALYST_STAGE_BY_ID.items():
        if analyst in selected_analysts or stage in skipped_by_stage:
            continue
        skipped_by_stage[stage] = "未选择该分析师。"
    if not include_risk:
        skipped_by_stage["risk_review"] = "用户关闭风险评估。"

    planned: list[StockStagePlanItem] = []
    for stage in _WORKFLOW_STAGE_ORDER:
        reason = skipped_by_stage.get(stage, "")
        planned.append(
            StockStagePlanItem(
                stage=stage,
                title=stock_stage_title(stage),
                status="skipped" if reason else "pending",
                reason=reason,
            )
        )
    return [item.model_dump() for item in planned]
