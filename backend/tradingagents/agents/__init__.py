import importlib
from typing import Dict, Tuple

from tradingagents.utils.logginginit import get_logger

logger = get_logger("default")

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "Toolkit": ("tradingagents.agents.utils.agentutils", "Toolkit"),
    "FinancialSituationMemory": ("tradingagents.agents.utils.memory", "FinancialSituationMemory"),
    "create_msg_delete": ("tradingagents.agents.utils.agentutils", "create_msg_delete"),
    "AgentState": ("tradingagents.agents.utils.agentstates", "AgentState"),
    "InvestDebateState": ("tradingagents.agents.utils.agentstates", "InvestDebateState"),
    "RiskDebateState": ("tradingagents.agents.utils.agentstates", "RiskDebateState"),
    "create_bear_researcher": ("tradingagents.agents.researchers.bearresearcher", "create_bear_researcher"),
    "create_bull_researcher": ("tradingagents.agents.researchers.bullresearcher", "create_bull_researcher"),
    "create_research_manager": ("tradingagents.agents.managers.researchmanager", "create_research_manager"),
    "create_portfolio_manager": ("tradingagents.agents.managers.portfoliomanager", "create_portfolio_manager"),
    "create_fundamentals_analyst": ("tradingagents.agents.analysts.fundamentalsanalyst", "create_fundamentals_analyst"),
    "create_market_analyst": ("tradingagents.agents.analysts.marketanalyst", "create_market_analyst"),
    "create_news_analyst": ("tradingagents.agents.analysts.newsanalyst", "create_news_analyst"),
    "create_social_media_analyst": ("tradingagents.agents.analysts.socialmediaanalyst", "create_social_media_analyst"),
    "create_sentiment_analyst": ("tradingagents.agents.analysts.sentimentanalyst", "create_sentiment_analyst"),
    "create_risky_debator": ("tradingagents.agents.riskmgmt.aggresivedebator", "create_risky_debator"),
    "create_safe_debator": ("tradingagents.agents.riskmgmt.conservativedebator", "create_safe_debator"),
    "create_neutral_debator": ("tradingagents.agents.riskmgmt.neutraldebator", "create_neutral_debator"),
    "create_risk_manager": ("tradingagents.agents.managers.riskmanager", "create_risk_manager"),
    "create_trader": ("tradingagents.agents.trader.trader", "create_trader"),
}

__all__ = [
    "Toolkit",
    "FinancialSituationMemory",
    "AgentState",
    "create_msg_delete",
    "InvestDebateState",
    "RiskDebateState",
    "create_bear_researcher",
    "create_bull_researcher",
    "create_research_manager",
    "create_fundamentals_analyst",
    "create_market_analyst",
    "create_neutral_debator",
    "create_news_analyst",
    "create_risky_debator",
    "create_risk_manager",
    "create_portfolio_manager",
    "create_safe_debator",
    "create_social_media_analyst",
    "create_sentiment_analyst",
    "create_trader",
]


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)

    module_name, attr_name = _EXPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals().keys()) | set(_EXPORTS.keys()))
