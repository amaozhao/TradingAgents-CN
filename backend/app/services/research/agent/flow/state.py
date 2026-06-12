from __future__ import annotations

from typing import Any, MutableMapping

from langgraph.graph.message import add_messages

from trader.graph.propagation import Propagator

REQUIRED_FINAL_FIELDS = (
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
    "performance_metrics",
)


def create_stock_initial_state(
    symbol: str,
    trade_date: str,
    *,
    asset_type: str = "stock",
    past_context: str = "",
    instrument_context: str = "",
) -> dict[str, Any]:
    return Propagator().create_initial_state(
        symbol,
        trade_date,
        asset_type=asset_type,
        past_context=past_context,
        instrument_context=instrument_context,
    )


def apply_node_update(
    state: MutableMapping[str, Any],
    update: MutableMapping[str, Any],
) -> None:
    for key, value in update.items():
        if key == "messages":
            state["messages"] = add_messages(state.get("messages", []), value)
            continue

        current = state.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            current.update(value)
            continue

        state[key] = value


def validate_final_state(state: MutableMapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_FINAL_FIELDS if not state.get(field)]
    if missing:
        raise ValueError(f"final state missing required fields: {', '.join(missing)}")
