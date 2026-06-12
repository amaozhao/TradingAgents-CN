"""
基本面分析师 - 统一工具架构版本
使用统一工具自动识别股票类型并调用相应数据源
"""

import importlib

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from trader.agents.risk.management.common import (
    get_risk_llm_timeout_seconds,
    invoke_with_timeout,
)
from trader.agents.utils.google import GoogleToolCallHandler
from trader.agents.utils.instruments import build_instrument_context
from trader.llm.clients import create_llm_client
from trader.utils.logging.init import get_logger
from trader.utils.logging.tools import log_analyst_module

logger = get_logger("default")

__all__ = [
    "AIMessage",
    "ChatPromptTemplate",
    "GoogleToolCallHandler",
    "MessagesPlaceholder",
    "ToolMessage",
    "build_instrument_context",
    "create_llm_client",
    "get_risk_llm_timeout_seconds",
    "importlib",
    "invoke_with_timeout",
    "log_analyst_module",
]
