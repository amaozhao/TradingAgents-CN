# ruff: noqa: F401,F403,F405,F821
# 标准库导入
import datetime
import importlib
import os
import re
import subprocess
import sys
from collections import deque
from difflib import get_close_matches
from functools import wraps
from pathlib import Path
from typing import Any, Optional, cast

# 第三方库导入
import typer
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# 项目内部导入
from app.core.config import settings
from cli.utils import (
    ensure_api_key,
    normalize_ticker_symbol,
    provider_default_url,
    select_analysts,
    select_deep_thinking_agent,
    select_llm_provider,
    select_research_depth,
    select_shallow_thinking_agent,
)
from trader.default import DEFAULT_CONFIG
from trader.graph.trading import TradingAgentsGraph
from trader.utils.logging.manager import get_logger

# 常量定义
DEFAULT_MESSAGE_BUFFER_SIZE = 100
DEFAULT_MAX_TOOL_ARGS_LENGTH = 100
DEFAULT_MAX_CONTENT_LENGTH = 200
DEFAULT_MAX_DISPLAY_MESSAGES = 12
DEFAULT_REFRESH_RATE = 4
DEFAULT_API_KEY_DISPLAY_LENGTH = 12

# 初始化日志系统
logger = get_logger("cli")


# CLI专用日志配置：禁用控制台输出，只保留文件日志
