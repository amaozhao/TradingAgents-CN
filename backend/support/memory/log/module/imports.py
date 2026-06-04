# ruff: noqa: F401,F403,F405,F821
"""Tests for TradingMemoryLog plus preserved CN role memory compatibility."""

import importlib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trader.agents.managers.portfolio import create_portfolio_manager
from trader.agents.schemas import PortfolioDecision, PortfolioRating
from trader.agents.utils.log import TradingMemoryLog
from trader.graph.propagation import Propagator
from trader.graph.reflection import Reflector
from trader.graph.trading import TradingAgentsGraph

_SEP = TradingMemoryLog._SEPARATOR

DECISION_BUY = "Rating: Buy\nEnter at $189-192, 6% portfolio cap."
DECISION_OVERWEIGHT = (
    "Rating: Overweight\n"
    "Executive Summary: Moderate position, await confirmation.\n"
    "Investment Thesis: Strong fundamentals but near-term headwinds."
)
DECISION_SELL = "Rating: Sell\nExit position immediately."
DECISION_NO_RATING = (
    "Executive Summary: Complex situation with multiple competing factors.\n"
    "Investment Thesis: No clear directional signal at this time."
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
