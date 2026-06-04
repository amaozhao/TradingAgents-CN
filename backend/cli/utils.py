import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import questionary
from dotenv import find_dotenv, set_key
from rich.console import Console

from cli.models import AnalystType, AssetType
from trader.llm.clients.keys import get_api_key_env
from trader.llm.clients.models import get_model_options
from trader.llm.clients.providers import default_backend_url, normalize_provider_key
from trader.utils.logging.manager import get_logger
from trader.utils.stocks import StockUtils

logger = get_logger("cli")
console = Console()

ANALYST_ORDER = [
    ("市场分析师 | Market Analyst", AnalystType.MARKET),
    ("社交媒体分析师 | Social Media Analyst", AnalystType.SOCIAL),
    ("新闻分析师 | News Analyst", AnalystType.NEWS),
    ("基本面分析师 | Fundamentals Analyst", AnalystType.FUNDAMENTALS),
]

CRYPTO_SUFFIXES = ("-USD", "-USDT", "-USDC", "-BTC", "-ETH")

PROVIDER_OPTIONS: List[Dict[str, str]] = [
    {
        "label": "阿里百炼 (DashScope)",
        "key": "qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    {
        "label": "DeepSeek",
        "key": "deepseek",
        "base_url": "https://api.deepseek.com",
    },
    {
        "label": "OpenAI",
        "key": "openai",
        "base_url": "https://api.openai.com/v1",
    },
    {
        "label": "🔧 自定义OpenAI端点",
        "key": "custom_openai",
        "base_url": "custom",
    },
    {
        "label": "Anthropic",
        "key": "anthropic",
        "base_url": "https://api.anthropic.com/",
    },
    {
        "label": "Google",
        "key": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    },
    {
        "label": "OpenRouter",
        "key": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
    },
    {
        "label": "AiHubMix",
        "key": "aihubmix",
        "base_url": "https://aihubmix.com/v1",
    },
    {
        "label": "Ollama",
        "key": "ollama",
        "base_url": "http://localhost:11434/v1",
    },
    {
        "label": "智谱 GLM",
        "key": "glm",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    },
    {
        "label": "xAI",
        "key": "xai",
        "base_url": "https://api.x.ai/v1",
    },
    {
        "label": "MiniMax",
        "key": "minimax-cn",
        "base_url": "https://api.minimaxi.com/v1",
    },
    {
        "label": "Azure OpenAI",
        "key": "azure",
        "base_url": "",
    },
    {
        "label": "千帆 Qianfan",
        "key": "qianfan",
        "base_url": "https://qianfan.baidubce.com/v2",
    },
    {
        "label": "硅基流动 SiliconFlow",
        "key": "siliconflow",
        "base_url": "https://api.siliconflow.cn/v1",
    },
]


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return ticker.strip().upper()


def detect_asset_type(ticker: str) -> AssetType:
    normalized_ticker = ticker.strip().upper()
    if normalized_ticker.endswith(CRYPTO_SUFFIXES):
        return AssetType.CRYPTO
    return AssetType.STOCK


def filter_analysts_for_asset_type(
    analysts: List[AnalystType], asset_type: AssetType
) -> List[AnalystType]:
    if asset_type != AssetType.CRYPTO:
        return analysts
    return [
        analyst
        for analyst in analysts
        if analyst != AnalystType.FUNDAMENTALS
    ]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        "请输入要分析的股票代码 | Enter the ticker symbol to analyze:",
        validate=lambda x: len(x.strip()) > 0 or "请输入有效的股票代码 | Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        logger.info("\n[red]未提供股票代码，退出程序... | No ticker symbol provided. Exiting...[/red]")
        exit(1)

    return normalize_ticker_symbol(ticker)


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    date = questionary.text(
        "请输入分析日期 (YYYY-MM-DD) | Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "请输入有效的日期格式 YYYY-MM-DD | Please enter a valid date in YYYY-MM-DD format.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        logger.info("\n[red]未提供日期，退出程序... | No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts(ticker: Optional[str] = None) -> List[AnalystType]:
    """Select analysts using an interactive checkbox."""
    available_analysts = ANALYST_ORDER.copy()

    if ticker and StockUtils.is_china_stock(ticker):
        available_analysts = [
            (display, value)
            for display, value in ANALYST_ORDER
            if value != AnalystType.SOCIAL
        ]
        console.print(f"[yellow]💡 检测到A股代码 {ticker}，社交媒体分析师不可用（国内数据源限制）[/yellow]")

    choices = questionary.checkbox(
        "选择您的分析师团队 | Select Your [Analysts Team]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in available_analysts
        ],
        instruction="\n- 按空格键选择/取消选择分析师 | Press Space to select/unselect analysts\n- 按 'a' 键全选/取消全选 | Press 'a' to select/unselect all\n- 按回车键完成选择 | Press Enter when done",
        validate=lambda x: len(x) > 0 or "您必须至少选择一个分析师 | You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        logger.info("\n[red]未选择分析师，退出程序... | No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""
    depth_options = [
        ("浅层 - 快速研究，少量辩论和策略讨论 | Shallow - Quick research, few debate rounds", 1),
        ("中等 - 中等程度，适度的辩论和策略讨论 | Medium - Moderate debate and strategy discussion", 3),
        ("深度 - 全面研究，深入的辩论和策略讨论 | Deep - Comprehensive research, in-depth debate", 5),
    ]

    choice = questionary.select(
        "选择您的研究深度 | Select Your [Research Depth]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in depth_options
        ],
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info("\n[red]未选择研究深度，退出程序... | No research depth selected. Exiting...[/red]")
        exit(1)

    return choice


def _prompt_custom_model_id() -> str:
    model_id = questionary.text(
        "请输入模型名称 | Enter model ID:",
        validate=lambda x: len(x.strip()) > 0 or "请输入模型名称 | Please enter a model ID.",
    ).ask()
    if not model_id:
        logger.info("\n[red]未输入模型名称，退出程序... | No model ID entered. Exiting...[/red]")
        exit(1)
    return model_id.strip()


def _select_model(provider: str, mode: str) -> str:
    options = get_model_options(provider, mode)
    choice = questionary.select(
        f"选择您的{'快速' if mode == 'quick' else '深度'}思考LLM引擎 | Select Your [{mode.title()}-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in options
        ],
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info(f"\n[red]未选择{mode}模型，退出程序... | No {mode} model selected. Exiting...[/red]")
        exit(1)

    if choice == "custom":
        return _prompt_custom_model_id()

    return choice


def select_shallow_thinking_agent(provider: str) -> str:
    return _select_model(provider, "quick")


def select_deep_thinking_agent(provider: str) -> str:
    return _select_model(provider, "deep")


def provider_default_url(provider_key: str) -> str | None:
    """Return the CLI default endpoint for a provider, matching config aliases."""
    key = normalize_provider_key(provider_key)
    if not key:
        return None
    known_keys = {item["key"] for item in PROVIDER_OPTIONS} | {
        "qwen-cn",
        "glm-cn",
        "minimax",
        "custom_openai",
    }
    if key not in known_keys:
        return None
    if key == "google":
        return None
    if key == "ollama":
        return os.environ.get("OLLAMA_BASE_URL") or default_backend_url(key)

    url = default_backend_url(key)
    if key == "azure" and not url:
        return None
    return url or None


def ensure_api_key(provider: str) -> str | None:
    """Ensure the provider API key exists, prompting and persisting when missing."""
    env_var = get_api_key_env(provider)
    if not env_var:
        return None

    existing = os.environ.get(env_var)
    if existing:
        return existing

    console.print(f"\n[yellow]{env_var} 未设置 | {env_var} is not set.[/yellow]")
    key = questionary.password(
        f"请输入 {env_var}，将保存到 .env | Paste {env_var} (will be saved to .env):",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()
    if not key:
        console.print(f"[red]跳过。API 调用会在设置 {env_var} 前失败。[/red]")
        return None

    env_path = find_dotenv(usecwd=True) or str(Path.cwd() / ".env")
    Path(env_path).touch(exist_ok=True)
    set_key(env_path, env_var, key)
    os.environ[env_var] = key
    console.print(f"[green]已保存 {env_var} 到 {env_path}[/green]")
    return key


def confirm_ollama_endpoint(url: str) -> None:
    """Print a concise confirmation and soft validation for the Ollama endpoint."""
    from_env = os.environ.get("OLLAMA_BASE_URL")
    origin = " (from OLLAMA_BASE_URL)" if from_env and from_env == url else ""
    console.print(f"Using Ollama at {url}{origin}")

    if not url.startswith(("http://", "https://")):
        console.print(
            "Note: endpoint is missing a scheme. "
            "Ollama usually expects http://<host>:11434/v1."
        )
        return
    if (
        ":11434" not in url
        and "://localhost" not in url
        and "://127.0.0.1" not in url
    ):
        console.print("Note: remote Ollama endpoints usually include port 11434.")


def ask_output_language() -> str:
    """Ask for the report output language."""
    choice = questionary.select(
        "选择报告输出语言 | Select output language:",
        choices=[
            questionary.Choice("中文 (默认) | Chinese", "Chinese"),
            questionary.Choice("English", "English"),
            questionary.Choice("日本語 | Japanese", "Japanese"),
            questionary.Choice("한국어 | Korean", "Korean"),
            questionary.Choice("自定义 | Custom", "custom"),
        ],
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()
    if choice == "custom":
        custom = questionary.text(
            "请输入语言名称 | Enter language name:",
            validate=lambda x: len(x.strip()) > 0 or "请输入语言名称 | Please enter a language name.",
        ).ask()
        return custom.strip() if custom else "Chinese"
    return choice or "Chinese"


def select_llm_provider() -> tuple[str, str]:
    """Select the LLM provider using interactive selection."""
    choice = questionary.select(
        "选择您的LLM提供商 | Select your LLM Provider:",
        choices=[
            questionary.Choice(item["label"], value=(item["key"], item["base_url"]))
            for item in PROVIDER_OPTIONS
        ],
        default=questionary.Choice(
            PROVIDER_OPTIONS[0]["label"],
            value=(PROVIDER_OPTIONS[0]["key"], PROVIDER_OPTIONS[0]["base_url"]),
        ),
        instruction="\n- 使用方向键导航 | Use arrow keys to navigate\n- 按回车键选择 | Press Enter to select\n- 🇨🇳 推荐使用阿里百炼 (默认选择)",
        style=questionary.Style(
            [
                ("selected", "fg:green noinherit"),
                ("highlighted", "fg:green noinherit"),
                ("pointer", "fg:green noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        logger.info("\n[red]未选择LLM提供商，退出程序... | No LLM provider selected. Exiting...[/red]")
        exit(1)

    provider_key, url = choice

    if url == "custom":
        custom_url = questionary.text(
            "请输入自定义OpenAI端点URL | Please enter custom OpenAI endpoint URL:",
            default="https://api.openai.com/v1",
            instruction="例如: https://api.openai.com/v1 或 http://localhost:8000/v1",
        ).ask()

        if not custom_url:
            logger.info("\n[red]未输入自定义URL，退出程序... | No custom URL entered. Exiting...[/red]")
            exit(1)

        url = custom_url.strip()
        os.environ["CUSTOM_OPENAI_BASE_URL"] = url

    logger.info(f"已选择LLM提供商 | Selected provider: {provider_key}\tURL: {url}")
    return provider_key, url
