import importlib
import json

# TradingAgents/graph/trading_graph.py
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from app.core.config import settings
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from trader.agents import Toolkit
from trader.agents.utils.log import TradingMemoryLog
from trader.agents.utils.memory import FinancialSituationMemory
from trader.agents.utils.utils import (
    build_instrument_context,
    resolve_instrument_identity,
)
from trader.default import DEFAULT_CONFIG
from trader.flows.config import set_config as set_dataflows_config
from trader.flows.interface import set_config as set_interface_config
from trader.flows.utils import safe_ticker_component
from trader.llm.clients import create_llm_client
from trader.llm.clients.providers import env_key_for_provider, normalize_provider_key
from trader.utils.logging.manager import get_logger

from ..checkpointer import (
    checkpoint_step,
    clear_checkpoint,
    get_checkpointer,
    thread_id,
)
from ..conditions import ConditionalLogic
from ..propagation import Propagator
from ..reflection import Reflector
from ..setup import GraphSetup
from ..signals import SignalProcessor

logger = get_logger("agents")


def _configured_provider_kwargs(config: Dict[str, Any], provider: str) -> Dict[str, Any]:
    provider_key = normalize_provider_key(provider)
    kwargs: Dict[str, Any] = {}

    if provider_key == "google" and config.get("google_thinking_level"):
        kwargs["thinking_level"] = config["google_thinking_level"]
    if provider_key == "openai" and config.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    if provider_key in {"anthropic", "minimax-token-plan"} and config.get("anthropic_effort"):
        kwargs["effort"] = config["anthropic_effort"]

    return kwargs


def create_llm_by_provider(
    *,
    provider: str,
    model: str,
    backend_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    llm_kwargs: Dict[str, Any] = dict(kwargs)
    if temperature is not None:
        llm_kwargs["temperature"] = temperature
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = max_tokens
    if timeout is not None:
        llm_kwargs["timeout"] = timeout
    if api_key:
        llm_kwargs["api_key"] = api_key

    return create_llm_client(
        provider=provider,
        model=model,
        base_url=backend_url or None,
        **llm_kwargs,
    ).get_llm()


def _create_provider_pair(
    *,
    provider: str,
    config: Dict[str, Any],
    quick_temperature: float,
    quick_max_tokens: int,
    quick_timeout: int,
    deep_temperature: float,
    deep_max_tokens: int,
    deep_timeout: int,
    backend_url: Optional[str] = None,
    api_key: Optional[str] = None,
    quick_extra_kwargs: Optional[Dict[str, Any]] = None,
    deep_extra_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    provider_key = normalize_provider_key(provider)
    base_url = backend_url or config.get("backend_url")
    provider_kwargs = _configured_provider_kwargs(config, provider_key)

    quick_kwargs = dict(provider_kwargs)
    quick_kwargs.update(quick_extra_kwargs or {})
    deep_kwargs = dict(provider_kwargs)
    deep_kwargs.update(deep_extra_kwargs or {})

    quick_api_key = config.get("quick_api_key") or api_key
    deep_api_key = config.get("deep_api_key") or api_key

    quick_llm = create_llm_by_provider(
        provider=provider_key,
        model=config["quick_think_llm"],
        backend_url=base_url,
        temperature=quick_temperature,
        max_tokens=quick_max_tokens,
        timeout=quick_timeout,
        api_key=quick_api_key,
        **quick_kwargs,
    )
    deep_llm = create_llm_by_provider(
        provider=provider_key,
        model=config["deep_think_llm"],
        backend_url=base_url,
        temperature=deep_temperature,
        max_tokens=deep_max_tokens,
        timeout=deep_timeout,
        api_key=deep_api_key,
        **deep_kwargs,
    )

    return deep_llm, quick_llm

__all__ = [
    "Any",
    "ChatOpenAI",
    "ConditionalLogic",
    "DEFAULT_CONFIG",
    "Dict",
    "FinancialSituationMemory",
    "GraphSetup",
    "List",
    "Optional",
    "Path",
    "Propagator",
    "Reflector",
    "SignalProcessor",
    "ToolNode",
    "Toolkit",
    "TradingMemoryLog",
    "Tuple",
    "_configured_provider_kwargs",
    "_create_provider_pair",
    "build_instrument_context",
    "cast",
    "checkpoint_step",
    "clear_checkpoint",
    "create_llm_by_provider",
    "create_llm_client",
    "datetime",
    "env_key_for_provider",
    "get_checkpointer",
    "get_logger",
    "importlib",
    "json",
    "logger",
    "normalize_provider_key",
    "os",
    "resolve_instrument_identity",
    "safe_ticker_component",
    "set_dataflows_config",
    "set_interface_config",
    "settings",
    "thread_id",
    "time",
    "timedelta",
]
