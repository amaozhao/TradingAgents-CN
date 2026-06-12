from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from trader.agents import FinancialSituationMemory, Toolkit
from trader.agents.utils.log import TradingMemoryLog
from trader.graph.conditions import ConditionalLogic
from trader.graph.propagation import Propagator
from trader.graph.reflection import Reflector
from trader.graph.signals import SignalProcessor

from .graph import DEFAULT_ANALYSTS


@dataclass(frozen=True)
class StockWorkflowRuntimeConfig:
    recursion_limit: int


@dataclass
class StockWorkflowContext:
    symbol: str
    trade_date: str
    asset_type: str
    selected_analysts: list[str]
    config: dict[str, Any]
    quick_llm: Any
    deep_llm: Any
    toolkit: Any
    bull_memory: Any | None
    bear_memory: Any | None
    trader_memory: Any | None
    invest_judge_memory: Any | None
    risk_manager_memory: Any | None
    conditional_logic: ConditionalLogic
    propagator: Propagator
    signal_processor: SignalProcessor
    memory_log: TradingMemoryLog
    reflector: Reflector
    runtime_config: StockWorkflowRuntimeConfig
    attempt_id: str | None = None
    task_id: str | None = None
    principal: Any | None = None
    curr_state: dict[str, Any] | None = None


def build_stock_workflow_context(
    *,
    symbol: str,
    trade_date: str,
    asset_type: str = "stock",
    selected_analysts: Iterable[str] | None = None,
    config: dict[str, Any] | None = None,
    quick_llm: Any,
    deep_llm: Any,
    toolkit: Any | None = None,
    attempt_id: str | None = None,
    task_id: str | None = None,
    principal: Any | None = None,
) -> StockWorkflowContext:
    workflow_config = dict(config or {})
    analyst_keys = list(selected_analysts or DEFAULT_ANALYSTS)
    runtime_config = StockWorkflowRuntimeConfig(
        recursion_limit=int(workflow_config.get("max_recur_limit", 100))
    )

    role_memories = _build_role_memories(workflow_config)

    return StockWorkflowContext(
        symbol=symbol,
        trade_date=str(trade_date),
        asset_type=asset_type,
        selected_analysts=analyst_keys,
        config=workflow_config,
        quick_llm=quick_llm,
        deep_llm=deep_llm,
        toolkit=toolkit or Toolkit(config=workflow_config),
        bull_memory=role_memories["bull_memory"],
        bear_memory=role_memories["bear_memory"],
        trader_memory=role_memories["trader_memory"],
        invest_judge_memory=role_memories["invest_judge_memory"],
        risk_manager_memory=role_memories["risk_manager_memory"],
        conditional_logic=ConditionalLogic(
            max_debate_rounds=workflow_config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=workflow_config.get(
                "max_risk_discuss_rounds", 1
            ),
        ),
        propagator=Propagator(max_recur_limit=runtime_config.recursion_limit),
        signal_processor=SignalProcessor(quick_llm),
        memory_log=TradingMemoryLog(workflow_config),
        reflector=Reflector(quick_llm),
        runtime_config=runtime_config,
        attempt_id=attempt_id,
        task_id=task_id,
        principal=principal,
    )


def _build_role_memories(config: dict[str, Any]) -> dict[str, Any | None]:
    names = (
        "bull_memory",
        "bear_memory",
        "trader_memory",
        "invest_judge_memory",
        "risk_manager_memory",
    )
    if config.get("memory_enabled", True) is False:
        return {name: None for name in names}
    return {name: FinancialSituationMemory(name, config) for name in names}
