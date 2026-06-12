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

# 项目内部导入
from app.core.config import settings
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
from trader.default import DEFAULT_CONFIG
from trader.graph.trading import TradingAgentsGraph
from trader.utils.logging.manager import get_logger

from cli.utils import (
    console,
    ensure_api_key,
    get_user_selections,
    normalize_ticker_symbol,
    provider_default_url,
    select_analysts,
    select_deep_thinking_agent,
    select_llm_provider,
    select_research_depth,
    select_shallow_thinking_agent,
)

# 常量定义
DEFAULT_MESSAGE_BUFFER_SIZE = 100
DEFAULT_MAX_TOOL_ARGS_LENGTH = 100
DEFAULT_MAX_CONTENT_LENGTH = 200
DEFAULT_MAX_DISPLAY_MESSAGES = 12
DEFAULT_REFRESH_RATE = 4
DEFAULT_API_KEY_DISPLAY_LENGTH = 12

# 初始化日志系统
logger = get_logger("cli")

app = typer.Typer(help="TradingAgents-CN 命令行工具 | CLI")


class CLIUserInterface:
    """Small console facade used by legacy CLI progress helpers."""

    def __init__(self, output_console: Console | None = None) -> None:
        self.console = output_console or console

    def show_user_message(self, message: str, style: str = "") -> None:
        self.console.print(message, style=style or None)

    def show_progress(self, message: str) -> None:
        self.console.print(f"[cyan]🔄 {message}[/cyan]")

    def show_success(self, message: str) -> None:
        self.console.print(f"[green]✅ {message}[/green]")

    def show_warning(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/yellow]")

    def show_error(self, message: str) -> None:
        self.console.print(f"[red]{message}[/red]")

    def show_step_header(self, step: int, title: str) -> None:
        self.console.print(f"\n[bold blue]步骤 {step}: {title}[/bold blue]")

    def show_data_info(self, label: str, value: str, detail: str = "") -> None:
        suffix = f" - {detail}" if detail else ""
        self.console.print(f"[cyan]{label}:[/cyan] [bold]{value}[/bold]{suffix}")


class MessageBuffer:
    """In-memory progress state rendered by the legacy live CLI."""

    def __init__(self) -> None:
        self.messages: deque[tuple[str, str]] = deque(maxlen=DEFAULT_MESSAGE_BUFFER_SIZE)
        self.tool_calls: deque[tuple[str, Any]] = deque(maxlen=DEFAULT_MESSAGE_BUFFER_SIZE)
        self.agent_status: dict[str, str] = {
            "Market Analyst": "pending",
            "Social Analyst": "pending",
            "News Analyst": "pending",
            "Fundamentals Analyst": "pending",
            "Bull Researcher": "pending",
            "Bear Researcher": "pending",
            "Research Manager": "pending",
            "Trader": "pending",
            "Risky Analyst": "pending",
            "Safe Analyst": "pending",
            "Neutral Analyst": "pending",
            "Portfolio Manager": "pending",
        }
        self.report_sections: dict[str, str | None] = {
            "market_report": None,
            "sentiment_report": None,
            "news_report": None,
            "fundamentals_report": None,
            "investment_plan": None,
            "trader_investment_plan": None,
            "final_trade_decision": None,
        }
        self.current_report: str | None = None
        self.final_report: str | None = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append((role, content))

    def add_tool_call(self, name: str, args: Any) -> None:
        self.tool_calls.append((name, args))

    def update_agent_status(self, agent: str, status: str) -> None:
        self.agent_status[agent] = status

    def update_report_section(self, section: str, content: str | None) -> None:
        self.report_sections[section] = content
        if content:
            self.current_report = content


ui = CLIUserInterface()
message_buffer = MessageBuffer()


def create_layout() -> Layout:
    layout = Layout()
    layout.split_column(Layout(name="main"), Layout(name="footer", size=3))
    layout["main"].split_row(Layout(name="status"), Layout(name="content"))
    return layout


def _status_table() -> Table:
    table = Table(title="Agent Status", box=box.SIMPLE)
    table.add_column("Agent")
    table.add_column("Status")
    for agent, status in message_buffer.agent_status.items():
        table.add_row(agent, status)
    return table


def _messages_panel() -> Panel:
    lines = [
        f"[bold]{role}:[/bold] {content}"
        for role, content in list(message_buffer.messages)[-DEFAULT_MAX_DISPLAY_MESSAGES:]
    ]
    return Panel("\n".join(lines) or "No messages yet", title="Messages")


def update_display(layout: Layout, spinner_text: str | None = None) -> None:
    layout["status"].update(_status_table())
    content = _messages_panel()
    if spinner_text:
        content = Panel(Spinner("dots", text=spinner_text), title="Progress")
    layout["content"].update(content)
    layout["footer"].update(Panel("TradingAgents-CN"))


# CLI专用日志配置：禁用控制台输出，只保留文件日志

__all__ = [
    "Align",
    "Columns",
    "DEFAULT_CONFIG",
    "Live",
    "Markdown",
    "Optional",
    "Path",
    "Text",
    "TradingAgentsGraph",
    "cast",
    "datetime",
    "ensure_api_key",
    "get_close_matches",
    "get_user_selections",
    "importlib",
    "normalize_ticker_symbol",
    "os",
    "provider_default_url",
    "re",
    "select_analysts",
    "select_deep_thinking_agent",
    "select_llm_provider",
    "select_research_depth",
    "select_shallow_thinking_agent",
    "settings",
    "subprocess",
    "sys",
    "wraps",
]
