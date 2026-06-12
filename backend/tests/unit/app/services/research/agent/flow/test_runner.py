from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.research.agent.flow.graph import build_stock_dag_parity_plan
from app.services.research.agent.flow.stages.analysts import AnalystStageRunner
from app.services.research.agent.flow.stages.decision import RiskDecisionRunner
from app.services.research.agent.flow.stages.research import ResearchDebateRunner
from app.services.research.agent.flow.stages.risk import RiskDebateRunner
from app.services.research.agent.flow.stages.trader import TraderDecisionRunner
from app.services.research.agent.flow.state import create_stock_initial_state
from trader.agents import create_msg_delete
from trader.graph.conditions import ConditionalLogic


class Recorder:
    def __init__(self):
        self.nodes = []
        self.edges = []


class FakeToolRunner:
    def run_tools(self, key, state):
        return {
            "messages": [
                ToolMessage(content=f"{key} tool result", tool_call_id="call-1")
            ]
        }


def _context():
    return SimpleNamespace(
        quick_llm=object(),
        deep_llm=object(),
        toolkit=object(),
        trader_memory=None,
        risk_manager_memory=None,
        conditional_logic=ConditionalLogic(
            max_debate_rounds=1,
            max_risk_discuss_rounds=1,
        ),
    )


def test_analyst_stage_runner_tool_loop():
    state = create_stock_initial_state(
        "600519",
        "2026-06-12",
        instrument_context="测试标的",
    )
    recorder = Recorder()
    calls = {"market": 0}

    def market_handler(_state):
        calls["market"] += 1
        if calls["market"] == 1:
            return {
                "messages": [
                    AIMessage(
                        content="",
                        id="market-ai-1",
                        tool_calls=[
                            {
                                "name": "get_stock_market_data_unified",
                                "args": {"symbol": "600519"},
                                "id": "call-1",
                            }
                        ],
                    )
                ]
            }
        return {
            "messages": [AIMessage(content="done", id="market-ai-2")],
            "market_report": "M" * 101,
            "market_tool_call_count": 1,
        }

    runner = AnalystStageRunner(
        _context(),
        recorder=recorder,
        agent_handlers={"market": market_handler},
        tool_runner=FakeToolRunner(),
        clear_handler=create_msg_delete(),
    )

    runner.run_selected_analysts(
        state,
        build_stock_dag_parity_plan(["market"], "risk_manager"),
    )

    assert recorder.nodes == [
        "Market Analyst",
        "tools_market",
        "Market Analyst",
        "Msg Clear Market",
    ]
    assert state["market_report"].startswith("M" * 101)
    assert state["market_tool_call_count"] == 1
    assert len(state["messages"]) == 1
    assert isinstance(state["messages"][0], HumanMessage)


def test_analyst_stage_runner_selected_order():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()

    def market_handler(_state):
        return {
            "messages": [AIMessage(content="market done", id="market-ai")],
            "market_report": "M" * 101,
        }

    def news_handler(_state):
        return {
            "messages": [AIMessage(content="news done", id="news-ai")],
            "news_report": "N" * 101,
        }

    runner = AnalystStageRunner(
        _context(),
        recorder=recorder,
        agent_handlers={"market": market_handler, "news": news_handler},
        tool_runner=FakeToolRunner(),
        clear_handler=create_msg_delete(),
    )

    next_node = runner.run_selected_analysts(
        state,
        build_stock_dag_parity_plan(["market", "news"], "risk_manager"),
    )

    assert recorder.nodes == [
        "Market Analyst",
        "Msg Clear Market",
        "News Analyst",
        "Msg Clear News",
    ]
    assert next_node == "Bull Researcher"


def test_research_debate_runner_matches_old_loop():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()

    def bull_handler(_state):
        return {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument",
                "bull_history": "\nBull Analyst: bull argument",
                "current_response": "Bull Analyst: bull argument",
                "count": 1,
            }
        }

    def bear_handler(_state):
        return {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument\nBear Analyst: bear argument",
                "bear_history": "\nBear Analyst: bear argument",
                "current_response": "Bear Analyst: bear argument",
                "count": 2,
            }
        }

    def manager_handler(_state):
        return {
            "investment_debate_state": {
                "judge_decision": "investment plan",
                "current_response": "investment plan",
            },
            "investment_plan": "investment plan",
        }

    runner = ResearchDebateRunner(
        _context(),
        recorder=recorder,
        handlers={
            "Bull Researcher": bull_handler,
            "Bear Researcher": bear_handler,
            "Research Manager": manager_handler,
        },
    )

    runner.run_until_manager(state)

    assert recorder.nodes == [
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
    ]
    assert state["investment_debate_state"]["count"] == 2
    assert state["investment_debate_state"]["bull_history"].startswith(
        "\nBull Analyst:"
    )
    assert state["investment_debate_state"]["bear_history"].startswith(
        "\nBear Analyst:"
    )
    assert state["investment_debate_state"]["judge_decision"] == "investment plan"
    assert state["investment_plan"] == "investment plan"


def test_trader_runner_updates_state():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()

    def trader_handler(_state):
        return {
            "messages": [AIMessage(content="trader plan", id="trader-ai")],
            "trader_investment_plan": "trader plan",
            "sender": "Trader",
        }

    runner = TraderDecisionRunner(
        _context(),
        recorder=recorder,
        handler=trader_handler,
    )

    runner.run_trader(state)

    assert recorder.nodes[-1] == "Trader"
    assert state["trader_investment_plan"] == "trader plan"
    assert state["sender"] == "Trader"


def test_risk_debate_runner_matches_old_loop():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()

    def risky_handler(_state):
        return {
            "risk_debate_state": {
                "history": "\nRisky Analyst: risky",
                "risky_history": "\nRisky Analyst: risky",
                "aggressive_history": "\nRisky Analyst: risky",
                "current_risky_response": "risky",
                "current_aggressive_response": "risky",
                "latest_speaker": "Risky",
                "count": 1,
            }
        }

    def safe_handler(_state):
        return {
            "risk_debate_state": {
                "history": "\nRisky Analyst: risky\nSafe Analyst: safe",
                "safe_history": "\nSafe Analyst: safe",
                "conservative_history": "\nSafe Analyst: safe",
                "current_safe_response": "safe",
                "current_conservative_response": "safe",
                "latest_speaker": "Safe",
                "count": 2,
            }
        }

    def neutral_handler(_state):
        return {
            "risk_debate_state": {
                "history": (
                    "\nRisky Analyst: risky\nSafe Analyst: safe"
                    "\nNeutral Analyst: neutral"
                ),
                "neutral_history": "\nNeutral Analyst: neutral",
                "current_neutral_response": "neutral",
                "latest_speaker": "Neutral",
                "count": 3,
            }
        }

    def judge_handler(_state):
        return {
            "risk_debate_state": {
                "judge_decision": "final decision",
                "latest_speaker": "Judge",
            },
            "final_trade_decision": "final decision",
        }

    decision_runner = RiskDecisionRunner(
        _context(),
        recorder=recorder,
        handlers={"Risk Judge": judge_handler},
    )
    runner = RiskDebateRunner(
        _context(),
        recorder=recorder,
        handlers={
            "Risky Analyst": risky_handler,
            "Safe Analyst": safe_handler,
            "Neutral Analyst": neutral_handler,
        },
        decision_runner=decision_runner,
    )

    runner.run_until_decision(
        state,
        build_stock_dag_parity_plan(["market"], "risk_manager"),
    )

    assert recorder.nodes == [
        "Risky Analyst",
        "Safe Analyst",
        "Neutral Analyst",
        "Risk Judge",
    ]
    assert state["risk_debate_state"]["count"] == 3
    assert state["risk_debate_state"]["latest_speaker"] == "Judge"
    assert state["risk_debate_state"]["risky_history"].startswith("\nRisky Analyst:")
    assert state["risk_debate_state"]["aggressive_history"] == (
        state["risk_debate_state"]["risky_history"]
    )
    assert state["risk_debate_state"]["safe_history"].startswith("\nSafe Analyst:")
    assert state["risk_debate_state"]["conservative_history"] == (
        state["risk_debate_state"]["safe_history"]
    )
    assert state["risk_debate_state"]["neutral_history"].startswith(
        "\nNeutral Analyst:"
    )
    assert state["final_trade_decision"] == "final decision"


def test_portfolio_manager_final_node():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()

    def portfolio_handler(_state):
        return {
            "risk_debate_state": {
                "judge_decision": "portfolio decision",
                "latest_speaker": "Judge",
            },
            "final_trade_decision": "portfolio decision",
        }

    runner = RiskDecisionRunner(
        _context(),
        recorder=recorder,
        handlers={"Portfolio Manager": portfolio_handler},
    )

    runner.run_final(
        state,
        build_stock_dag_parity_plan(["market"], "portfolio_manager"),
    )

    assert recorder.nodes[-1] == "Portfolio Manager"
    assert state["risk_debate_state"]["latest_speaker"] == "Judge"
    assert state["final_trade_decision"] == "portfolio decision"


def test_include_risk_false_bypasses_risk_nodes():
    state = create_stock_initial_state("600519", "2026-06-12")
    recorder = Recorder()
    plan = build_stock_dag_parity_plan(
        selected_analysts=["market"],
        final_decision_engine="risk_manager",
        include_risk=False,
    )
    decision_runner = RiskDecisionRunner(_context(), recorder=recorder)
    runner = RiskDebateRunner(
        _context(),
        recorder=recorder,
        decision_runner=decision_runner,
    )

    runner.run_after_trader(state, plan)

    assert "Risky Analyst" not in recorder.nodes
    assert "Safe Analyst" not in recorder.nodes
    assert "Neutral Analyst" not in recorder.nodes
    assert "Risk Judge" not in recorder.nodes
    assert "Portfolio Manager" not in recorder.nodes
    assert recorder.edges[-1] == ("Trader", "END")
