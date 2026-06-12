import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from app.services.research.agent.flow.state import (
    apply_node_update,
    create_stock_initial_state,
    validate_final_state,
)
from trader.graph.propagation import Propagator


def test_initial_state_matches_old_propagator_contract():
    old_state = Propagator().create_initial_state(
        "600519",
        "2026-06-12",
        asset_type="stock",
        past_context="past",
        instrument_context="instrument",
    )
    new_state = create_stock_initial_state(
        "600519",
        "2026-06-12",
        asset_type="stock",
        past_context="past",
        instrument_context="instrument",
    )

    assert new_state["company_of_interest"] == old_state["company_of_interest"]
    assert new_state["asset_type"] == old_state["asset_type"]
    assert new_state["instrument_context"] == old_state["instrument_context"]
    assert new_state["trade_date"] == old_state["trade_date"]
    assert new_state["past_context"] == old_state["past_context"]
    assert new_state["investment_debate_state"] == old_state["investment_debate_state"]
    assert new_state["risk_debate_state"] == old_state["risk_debate_state"]
    assert new_state["market_tool_call_count"] == 0
    assert new_state["news_tool_call_count"] == 0
    assert new_state["sentiment_tool_call_count"] == 0
    assert new_state["fundamentals_tool_call_count"] == 0


def test_message_updates_use_langgraph_add_messages_semantics():
    state = create_stock_initial_state("600519", "2026-06-12")
    first = state["messages"][0]
    ai = AIMessage(content="analysis", id="ai-1")

    apply_node_update(state, {"messages": [ai]})

    assert [message.id for message in state["messages"]] == [first.id, "ai-1"]

    apply_node_update(
        state,
        {
            "messages": [
                RemoveMessage(id=first.id),
                RemoveMessage(id="ai-1"),
                HumanMessage(content="继续分析，不要改变分析标的。", id="placeholder"),
            ]
        },
    )

    assert [message.id for message in state["messages"]] == ["placeholder"]


def test_scalar_and_nested_state_updates_are_applied_in_place():
    state = create_stock_initial_state("600519", "2026-06-12")

    apply_node_update(
        state,
        {
            "market_report": "market report",
            "market_tool_call_count": 1,
            "investment_debate_state": {
                "history": "\nBull Analyst: text",
                "bull_history": "\nBull Analyst: text",
                "bear_history": "",
                "current_response": "Bull Analyst: text",
                "count": 1,
            },
        },
    )

    assert state["market_report"] == "market report"
    assert state["market_tool_call_count"] == 1
    assert state["investment_debate_state"]["current_response"].startswith("Bull")
    assert state["investment_debate_state"]["count"] == 1


def test_validate_final_state_requires_old_final_fields():
    state = create_stock_initial_state("600519", "2026-06-12")

    with pytest.raises(ValueError, match="investment_plan"):
        validate_final_state(state)

    state["investment_plan"] = "investment"
    state["trader_investment_plan"] = "trader"
    state["final_trade_decision"] = "decision"
    state["performance_metrics"] = {"node_count": 1}

    validate_final_state(state)
