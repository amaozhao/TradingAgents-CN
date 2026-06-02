"""Compatibility import path for legacy agent graph helpers."""

from __future__ import annotations

from typing import Any

from tradingagents.graph.trading_graph import TradingAgentsGraph


def create_trading_graph(*args: Any, **kwargs: Any):
    """Create and return the compiled trading graph used by older scripts."""
    return TradingAgentsGraph(*args, **kwargs).graph


__all__ = ["TradingAgentsGraph", "create_trading_graph"]
