import importlib
from typing import Dict, Tuple

from trader.utils.logging.init import get_logger

logger = get_logger("default")

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "Toolkit": ("trader.agents.utils.utils", "Toolkit"),
    "FinancialSituationMemory": ("trader.agents.utils.memory", "FinancialSituationMemory"),
    "create_msg_delete": ("trader.agents.utils.utils", "create_msg_delete"),
    "AgentState": ("trader.agents.utils.states", "AgentState"),
    "InvestDebateState": ("trader.agents.utils.states", "InvestDebateState"),
    "RiskDebateState": ("trader.agents.utils.states", "RiskDebateState"),
    "create_bear_researcher": ("trader.agents.researchers.bear", "create_bear_researcher"),
    "create_bull_researcher": ("trader.agents.researchers.bull", "create_bull_researcher"),
    "create_research_manager": ("trader.agents.managers.research", "create_research_manager"),
    "create_portfolio_manager": ("trader.agents.managers.portfolio", "create_portfolio_manager"),
    "create_fundamentals_analyst": ("trader.agents.analysts.fundamentals", "create_fundamentals_analyst"),
    "create_market_analyst": ("trader.agents.analysts.market", "create_market_analyst"),
    "create_news_analyst": ("trader.agents.analysts.news", "create_news_analyst"),
    "create_social_media_analyst": ("trader.agents.analysts.social", "create_social_media_analyst"),
    "create_sentiment_analyst": ("trader.agents.analysts.sentiment", "create_sentiment_analyst"),
    "create_risky_debator": ("trader.agents.risk.management.risky", "create_risky_debator"),
    "create_safe_debator": ("trader.agents.risk.management.conservative", "create_safe_debator"),
    "create_neutral_debator": ("trader.agents.risk.management.neutral", "create_neutral_debator"),
    "create_risk_manager": ("trader.agents.managers.risk", "create_risk_manager"),
    "create_trader": ("trader.agents.trader.trader", "create_trader"),
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
