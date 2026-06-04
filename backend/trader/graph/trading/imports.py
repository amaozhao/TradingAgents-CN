# ruff: noqa: F401,F403,F405,F821
import importlib
import json

# TradingAgents/graph/trading_graph.py
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

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
