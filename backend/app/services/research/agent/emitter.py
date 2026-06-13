from __future__ import annotations

import logging
from asyncio import get_running_loop, run_coroutine_threadsafe
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from .context import ToolExecutionContext
from .stage import stock_stage_title


logger = logging.getLogger("app.services.research.agent.stock")


_NODE_STAGE = {
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


class StockWorkflowEventAdapter:
    @staticmethod
    async def emit_stage(
        *,
        context: ToolExecutionContext,
        task_id: str,
        stage: str,
        status: str,
        progress: int,
        message: str,
        batch_id: str | None = None,
    ) -> None:
        if context.event_emitter is None:
            return
        event: dict[str, Any] = {
            "tool_name": "stock_analysis",
            "mode": "single",
            "stage": stage,
            "title": stock_stage_title(stage),
            "status": status,
            "progress": progress,
            "message": message,
            "task_id": task_id,
            "attempt_id": context.request_id,
        }
        if batch_id:
            event["batch_id"] = batch_id
        await context.event_emitter(event)

    @staticmethod
    def node_emitter(
        *,
        context: ToolExecutionContext,
        task_id: str,
        batch_id: str | None = None,
    ):
        event_emitter = context.event_emitter
        if event_emitter is None:
            return None
        loop = get_running_loop()

        def emit(node: str, previous: str | None) -> None:
            stage = _NODE_STAGE.get(node, "agent_summary")
            event = {
                "tool_name": "stock_analysis",
                "mode": "single",
                "stage": stage,
                "title": stock_stage_title(stage),
                "status": "completed",
                "progress": stock_stage_progress(stage),
                "message": f"{stock_stage_title(stage)}已完成。",
                "task_id": task_id,
                "attempt_id": context.request_id,
                "node": node,
                "edge_from": previous,
                "edge_to": node,
            }
            if batch_id:
                event["batch_id"] = batch_id
            try:
                future = run_coroutine_threadsafe(event_emitter(event), loop)
                future.result(timeout=5)
            except FutureTimeoutError:
                logger.warning("Timed out emitting stock workflow stage event: %s", node)
            except Exception as exc:
                logger.warning(
                    "Failed to emit stock workflow stage event %s: %s", node, exc
                )

        return emit


def stock_stage_progress(stage: str) -> int:
    progress_by_stage = {
        "validate_input": 8,
        "prepare_state": 12,
        "market_analysis": 30,
        "sentiment_analysis": 45,
        "news_analysis": 55,
        "fundamentals_analysis": 65,
        "research_debate": 75,
        "research_manager": 82,
        "trader_decision": 88,
        "risk_debate": 94,
        "final_risk_decision": 97,
        "report_generation": 99,
        "agent_summary": 100,
    }
    return progress_by_stage.get(stage, 0)
