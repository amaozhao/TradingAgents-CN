import importlib
# TradingAgents/graph/propagation.py

from typing import Dict, Any, List, Optional

# 导入统一日志系统
from trader.utils.logging.init import get_logger
logger = get_logger("default")
from trader.agents.utils.states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        asset_type: str = "stock",
        past_context: str = "",
        instrument_context: str = "",
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        HumanMessage = getattr(importlib.import_module('langchain_core.messages'), 'HumanMessage')

        # 🔥 修复：创建明确的分析请求消息，而不是只传递股票代码
        # 这样可以确保所有LLM（包括DeepSeek）都能理解任务
        analysis_request = f"请对股票 {company_name} 进行全面分析，交易日期为 {trade_date}。"

        return {
            "messages": [HumanMessage(content=analysis_request)],
            "company_of_interest": company_name,
            "asset_type": asset_type,
            "instrument_context": instrument_context,
            "trade_date": str(trade_date),
            "past_context": past_context,
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "risky_history": "",
                    "aggressive_history": "",
                    "safe_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_risky_response": "",
                    "current_aggressive_response": "",
                    "current_safe_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
            "market_tool_call_count": 0,
            "news_tool_call_count": 0,
            "sentiment_tool_call_count": 0,
            "fundamentals_tool_call_count": 0,
        }

    def get_graph_args(
        self,
        use_progress_callback: bool = False,
        callbacks: Optional[List] = None,
    ) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            use_progress_callback: If True, use 'updates' mode for node-level progress tracking.
                                  If False, use 'values' mode for complete state updates.
        """
        # 使用 'updates' 模式可以获取节点级别的更新，用于进度跟踪
        # 使用 'values' 模式可以获取完整的状态更新
        stream_mode = "updates" if use_progress_callback else "values"

        config: Dict[str, Any] = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks

        return {
            "stream_mode": stream_mode,
            "config": config,
        }
