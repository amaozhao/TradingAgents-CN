# ruff: noqa: F401,F403,F405,F821,F722
import functools
import importlib
from datetime import datetime
from typing import Annotated, Any, Mapping, Optional

import yfinance as yf
from langchain_core.messages import (
    HumanMessage,
    RemoveMessage,
)
from langchain_core.tools import tool

import trader.flows.interface as interface
from trader.default import DEFAULT_CONFIG

# 导入统一日志系统和工具日志装饰器
from trader.utils.logging.manager import get_logger
from trader.utils.logging.tools import log_tool_call

logger = get_logger("agents")
