#!/usr/bin/env python3
"""
TradingAgents-CN 核心模块

这是一个基于多智能体的股票分析系统，支持A股、港股和美股的综合分析。
"""

__version__ = "1.0.1"
__author__ = "TradingAgents-CN Team"
__description__ = "Multi-agent stock analysis system for Chinese markets"

def __getattr__(name):
    """Lazy compatibility exports without initializing config/logging on import."""
    if name == "config_manager":
        from .config import config_manager

        return config_manager
    if name == "logging_manager":
        from .utils.logging import manager as logging_manager

        return logging_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "config_manager",
    "logging_manager",
]
