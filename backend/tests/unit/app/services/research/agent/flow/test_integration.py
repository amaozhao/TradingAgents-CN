import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app.services.research.agent.flow import context as flow_context
from app.services.research.agent.flow.events import (
    StockWorkflowEventEmitter,
    build_stock_workflow_stage_events,
)
from app.services.research.agent.flow.graph import build_stock_dag_parity_plan
from app.services.research.agent.flow import runner as runner_module
from app.services.research.agent.flow.runner import StockDagParityWorkflow
from app.services.research.agent.flow.state import create_stock_initial_state
from trader.agents import create_msg_delete
from trader.graph.conditions import ConditionalLogic


class FakeDeepLLM:
    model_name = "fake-deep"


class FakeMemoryLog:
    def __init__(self, *_args, **_kwargs):
        self.get_past_context_called_with = None
        self.store_decision_called_with = None

    def get_past_context(self, ticker):
        self.get_past_context_called_with = ticker
        return "past context"

    def store_decision(self, **kwargs):
        self.store_decision_called_with = kwargs


class FakeSignalProcessor:
    def __init__(self, *_args, **_kwargs):
        pass

    def process_signal(self, full_signal, stock_symbol=None):
        return {
            "action": "持有",
            "confidence": 0.7,
            "risk_score": 0.3,
            "target_price": 123.0,
            "reasoning": f"{stock_symbol}:{full_signal}",
        }


class FakeMemory:
    def __init__(self, name, config):
        self.name = name
        self.config = config


class FakePendingMemoryLog(FakeMemoryLog):
    def __init__(self):
        super().__init__()
        self.batch_updates = None

    def get_pending_entries(self):
        return [
            {
                "ticker": "600519",
                "date": "2026-06-01",
                "decision": "previous decision",
            },
            {
                "ticker": "AAPL",
                "date": "2026-06-01",
                "decision": "other decision",
            },
        ]

    def batch_update_with_outcomes(self, updates):
        self.batch_updates = updates


class FakeReflector:
    def reflect_on_final_decision(
        self,
        *,
        final_decision,
        raw_return,
        alpha_return,
        benchmark_name,
    ):
        return f"{benchmark_name}:{raw_return}:{alpha_return}:{final_decision}"


def test_finish_hooks_match_old_runtime_contract():
    state = create_stock_initial_state("600519", "2026-06-12")
    state.update(
        {
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "investment",
            "trader_investment_plan": "trader",
            "final_trade_decision": "final decision",
        }
    )
    memory_log = FakeMemoryLog()
    context = SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        task_id="task-1",
        config={
            "llm_provider": "fake-provider",
            "deep_think_llm": "deep",
            "quick_think_llm": "quick",
        },
        memory_log=memory_log,
        signal_processor=FakeSignalProcessor(),
        deep_llm=FakeDeepLLM(),
        curr_state=None,
    )

    def executor():
        return (
            state,
            {
                "Market Analyst": 1.0,
                "tools_market": 0.5,
                "Msg Clear Market": 0.25,
                "Bull Researcher": 1.5,
                "Trader": 0.75,
                "Risk Judge": 1.25,
            },
            5.25,
        )

    result = StockDagParityWorkflow(context, executor=executor).run()

    metrics = state["performance_metrics"]
    assert metrics["node_count"] == len(metrics["node_timings"])
    assert set(metrics["category_timings"]) == {
        "analyst_team",
        "tool_calls",
        "message_clearing",
        "research_team",
        "trader_team",
        "risk_management_team",
        "other",
    }
    assert metrics["llm_config"]["provider"] == "fake-provider"
    assert memory_log.get_past_context_called_with == "600519"
    assert memory_log.store_decision_called_with == {
        "ticker": "600519",
        "trade_date": "2026-06-12",
        "final_trade_decision": state["final_trade_decision"],
    }
    assert result.state is state
    assert result.task_id == "task-1"
    assert result.decision["model_info"].startswith("FakeDeepLLM")
    assert {"action", "confidence", "risk_score", "target_price", "reasoning"} <= set(
        result.decision
    )
    assert context.curr_state is state


def test_finish_hooks_write_state_log_snapshot(tmp_path: Path):
    state = create_stock_initial_state("600519", "2026-06-12")
    state.update(
        {
            "market_report": "market report content",
            "sentiment_report": "sentiment report content",
            "news_report": "news report content",
            "fundamentals_report": "fundamentals report content",
            "investment_debate_state": {
                "bull_history": "Bull Analyst: content",
                "bear_history": "Bear Analyst: content",
                "history": "debate history",
                "current_response": "Research Manager: content",
                "judge_decision": "research decision content",
                "count": 2,
            },
            "risk_debate_state": {
                "risky_history": "Risky Analyst: content",
                "safe_history": "Safe Analyst: content",
                "neutral_history": "Neutral Analyst: content",
                "history": "risk history",
                "judge_decision": "risk decision content",
                "count": 3,
            },
            "investment_plan": "investment plan content",
            "trader_investment_plan": "trader plan content",
            "final_trade_decision": "final decision content",
        }
    )
    context = SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        task_id="task-state-log",
        selected_analysts=["market"],
        config={
            "llm_provider": "fake-provider",
            "state_log_dir": str(tmp_path),
        },
        memory_log=FakeMemoryLog(),
        signal_processor=FakeSignalProcessor(),
        deep_llm=FakeDeepLLM(),
        curr_state=None,
    )

    def executor():
        return state, {"Market Analyst": 0.1, "Risk Judge": 0.2}, 0.3

    StockDagParityWorkflow(context, executor=executor).run()

    state_log = (
        tmp_path / "600519" / "TradingAgentsStrategy_logs" / "full_states_log.json"
    )
    payload = json.loads(state_log.read_text())
    assert payload["2026-06-12"]["company_of_interest"] == "600519"
    assert payload["2026-06-12"]["final_trade_decision"] == "final decision content"


def test_workflow_runs_with_context_factory_and_records_current_state(monkeypatch):
    monkeypatch.setattr(flow_context, "FinancialSituationMemory", FakeMemory)
    monkeypatch.setattr(flow_context, "TradingMemoryLog", FakeMemoryLog)
    monkeypatch.setattr(flow_context, "SignalProcessor", FakeSignalProcessor)

    context = flow_context.build_stock_workflow_context(
        symbol="600519",
        trade_date="2026-06-12",
        selected_analysts=["market"],
        config={
            "llm_provider": "fake-provider",
            "memory_enabled": True,
        },
        quick_llm=object(),
        deep_llm=FakeDeepLLM(),
    )
    state = create_stock_initial_state("600519", "2026-06-12")
    state.update(
        {
            "market_report": "market report content",
            "investment_plan": "investment plan content",
            "trader_investment_plan": "trader plan content",
            "final_trade_decision": "final decision content",
        }
    )

    def executor():
        return state, {"Market Analyst": 0.1, "Risk Judge": 0.2}, 0.3

    result = StockDagParityWorkflow(context, executor=executor).run()

    assert result.status == "completed"
    assert context.curr_state is state
    assert context.memory_log.store_decision_called_with == {
        "ticker": "600519",
        "trade_date": "2026-06-12",
        "final_trade_decision": "final decision content",
    }


def test_workflow_resolves_pending_memory_entries_before_run(monkeypatch):
    memory_log = FakePendingMemoryLog()
    monkeypatch.setattr(
        runner_module,
        "_fetch_pending_returns",
        lambda _context, _ticker, _date, _benchmark: (0.12, 0.04, 5),
        raising=False,
    )
    context = SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        task_id="task-pending",
        selected_analysts=["market"],
        config={"llm_provider": "fake-provider"},
        memory_log=memory_log,
        reflector=FakeReflector(),
        signal_processor=FakeSignalProcessor(),
        deep_llm=FakeDeepLLM(),
        curr_state=None,
    )
    state = create_stock_initial_state("600519", "2026-06-12")
    state.update(
        {
            "market_report": "market report content",
            "investment_plan": "investment plan content",
            "trader_investment_plan": "trader plan content",
            "final_trade_decision": "final decision content",
        }
    )

    def executor():
        return state, {"Market Analyst": 0.1, "Risk Judge": 0.2}, 0.3

    StockDagParityWorkflow(context, executor=executor).run()

    assert memory_log.batch_updates == [
        {
            "ticker": "600519",
            "trade_date": "2026-06-01",
            "raw_return": 0.12,
            "alpha_return": 0.04,
            "holding_days": 5,
            "reflection": "SPY:0.12:0.04:previous decision",
        }
    ]


def test_node_and_stage_events_are_attempt_scoped():
    emitter = StockWorkflowEventEmitter(
        task_id="task-1",
        analysis_id="analysis-1",
        attempt_id="attempt-1",
    )

    event = emitter.node_event(
        node="Bull Researcher",
        status="completed",
        edge_from="Msg Clear Fundamentals",
        edge_to="Bear Researcher",
        report_keys_added=["bull_researcher"],
    )

    assert event["event_type"] == "stock_analysis.node"
    assert event["node"] == "Bull Researcher"
    assert event["stage"] == "research_debate"
    assert event["status"] in {"running", "completed", "failed", "skipped"}
    assert event["edge_from"] == "Msg Clear Fundamentals"
    assert event["edge_to"] == "Bear Researcher"
    assert event["task_id"] == "task-1"
    assert event["analysis_id"] == "analysis-1"
    assert event["attempt_id"] == "attempt-1"
    assert event["report_keys_added"] == ["bull_researcher"]


def test_stage_events_use_dag_parity_order():
    plan = build_stock_dag_parity_plan(
        ["market", "social", "news", "fundamentals"],
        "risk_manager",
    )
    stage_events = build_stock_workflow_stage_events(
        plan=plan,
        reports={
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "investment_plan": "investment",
            "trader_investment_plan": "trader",
            "risk_management_decision": "risk",
        },
        task_id="task-1",
        analysis_id="analysis-1",
        attempt_id="attempt-1",
    )

    assert [stage["stage"] for stage in stage_events] == [
        "validate_input",
        "prepare_state",
        "market_analysis",
        "sentiment_analysis",
        "news_analysis",
        "fundamentals_analysis",
        "research_debate",
        "research_manager",
        "trader_decision",
        "risk_debate",
        "final_risk_decision",
        "report_generation",
        "agent_summary",
    ]
    assert {event["attempt_id"] for event in stage_events} == {"attempt-1"}
    assert all(event["event_type"] == "stock_analysis.stage" for event in stage_events)


def test_skipped_stage_events_do_not_fabricate_unselected_reports():
    plan = build_stock_dag_parity_plan(
        selected_analysts=["market"],
        final_decision_engine="risk_manager",
        include_risk=False,
    )
    report = {"reports": {"market_report": "market only"}}

    stage_events = build_stock_workflow_stage_events(
        plan=plan,
        reports=report["reports"],
        task_id="task-1",
        analysis_id="analysis-1",
        attempt_id="attempt-1",
    )

    assert {"sentiment_analysis", "news_analysis", "fundamentals_analysis"} <= {
        event["stage"] for event in stage_events if event["status"] == "skipped"
    }
    assert "sentiment_report" not in report["reports"]
    assert "news_report" not in report["reports"]
    assert "fundamentals_report" not in report["reports"]
    assert all(
        "native" not in event.get("message", "").lower() for event in stage_events
    )
    assert any(
        event["stage"] == "risk_debate" and event["status"] == "skipped"
        for event in stage_events
    )
    assert "risk_management_decision" not in report["reports"]


def test_full_fake_workflow_runs_default_executor_with_all_nodes():
    context = SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        task_id="task-1",
        selected_analysts=["market", "social", "news", "fundamentals"],
        config={
            "llm_provider": "fake-provider",
            "deep_think_llm": "deep",
            "quick_think_llm": "quick",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "include_risk": True,
        },
        conditional_logic=ConditionalLogic(
            max_debate_rounds=1,
            max_risk_discuss_rounds=1,
        ),
        toolkit=object(),
        bull_memory=None,
        bear_memory=None,
        trader_memory=None,
        invest_judge_memory=None,
        risk_manager_memory=None,
        memory_log=FakeMemoryLog(),
        signal_processor=FakeSignalProcessor(),
        deep_llm=FakeDeepLLM(),
        quick_llm=object(),
        curr_state=None,
        clear_handler=create_msg_delete(),
        tool_runner=SimpleNamespace(),
    )

    context.agent_handlers = {
        key: _analyst_handler(report_key, content)
        for key, report_key, content in [
            ("market", "market_report", "M" * 101),
            ("social", "sentiment_report", "S" * 101),
            ("news", "news_report", "N" * 101),
            ("fundamentals", "fundamentals_report", "F" * 101),
        ]
    }
    context.research_handlers = {
        "Bull Researcher": lambda _state: {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument",
                "bull_history": "\nBull Analyst: bull argument",
                "current_response": "Bull Analyst: bull argument",
                "count": 1,
            }
        },
        "Bear Researcher": lambda _state: {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument\nBear Analyst: bear argument",
                "bear_history": "\nBear Analyst: bear argument",
                "current_response": "Bear Analyst: bear argument",
                "count": 2,
            }
        },
        "Research Manager": lambda _state: {
            "investment_debate_state": {
                "judge_decision": "research team decision content",
                "current_response": "research team decision content",
            },
            "investment_plan": "investment plan content",
        },
    }
    context.trader_handler = lambda _state: {
        "messages": [AIMessage(content="trader plan", id="trader-ai")],
        "trader_investment_plan": "trader investment plan content",
        "sender": "Trader",
    }
    context.risk_handlers = {
        "Risky Analyst": lambda _state: {
            "risk_debate_state": {
                "history": "\nRisky Analyst: risky",
                "risky_history": "\nRisky Analyst: risky",
                "aggressive_history": "\nRisky Analyst: risky",
                "current_risky_response": "risky",
                "current_aggressive_response": "risky",
                "latest_speaker": "Risky",
                "count": 1,
            }
        },
        "Safe Analyst": lambda _state: {
            "risk_debate_state": {
                "history": "\nRisky Analyst: risky\nSafe Analyst: safe",
                "safe_history": "\nSafe Analyst: safe",
                "conservative_history": "\nSafe Analyst: safe",
                "current_safe_response": "safe",
                "current_conservative_response": "safe",
                "latest_speaker": "Safe",
                "count": 2,
            }
        },
        "Neutral Analyst": lambda _state: {
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
        },
    }
    context.risk_decision_handlers = {
        "Risk Judge": lambda _state: {
            "risk_debate_state": {
                "judge_decision": "risk management decision content",
                "latest_speaker": "Judge",
            },
            "final_trade_decision": "final trade decision content",
        }
    }

    result = StockDagParityWorkflow(context).run()

    assert result.status == "completed"
    assert result.source == "agent_workflow_dag_parity"
    assert result.state["market_report"]
    assert result.state["sentiment_report"]
    assert result.state["news_report"]
    assert result.state["fundamentals_report"]
    assert result.state["investment_plan"]
    assert result.state["trader_investment_plan"]
    assert result.state["final_trade_decision"]
    assert result.report["reports"]["risk_management_decision"]
    assert len(result.report["reports"]) >= 14
    assert "bull_researcher" in result.report["reports"]
    assert result.node_events
    assert result.stage_events
    assert result.node_names == [
        "Market Analyst",
        "Msg Clear Market",
        "Sentiment Analyst",
        "Msg Clear Social",
        "News Analyst",
        "Msg Clear News",
        "Fundamentals Analyst",
        "Msg Clear Fundamentals",
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
        "Trader",
        "Risky Analyst",
        "Safe Analyst",
        "Neutral Analyst",
        "Risk Judge",
        "END",
    ]


def test_include_risk_false_default_workflow_skips_risk_and_uses_trader_decision():
    context = SimpleNamespace(
        symbol="600519",
        trade_date="2026-06-12",
        task_id="task-no-risk",
        selected_analysts=["market"],
        config={
            "llm_provider": "fake-provider",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "include_risk": False,
        },
        conditional_logic=ConditionalLogic(
            max_debate_rounds=1,
            max_risk_discuss_rounds=1,
        ),
        toolkit=object(),
        bull_memory=None,
        bear_memory=None,
        trader_memory=None,
        invest_judge_memory=None,
        risk_manager_memory=None,
        memory_log=FakeMemoryLog(),
        signal_processor=FakeSignalProcessor(),
        deep_llm=FakeDeepLLM(),
        quick_llm=object(),
        curr_state=None,
        clear_handler=create_msg_delete(),
        tool_runner=SimpleNamespace(),
    )
    context.agent_handlers = {
        "market": _analyst_handler("market_report", "M" * 101),
    }
    context.research_handlers = {
        "Bull Researcher": lambda _state: {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument",
                "bull_history": "\nBull Analyst: bull argument",
                "current_response": "Bull Analyst: bull argument",
                "count": 1,
            }
        },
        "Bear Researcher": lambda _state: {
            "investment_debate_state": {
                "history": "\nBull Analyst: bull argument\nBear Analyst: bear argument",
                "bear_history": "\nBear Analyst: bear argument",
                "current_response": "Bear Analyst: bear argument",
                "count": 2,
            }
        },
        "Research Manager": lambda _state: {
            "investment_debate_state": {
                "judge_decision": "research team decision content",
                "current_response": "research team decision content",
            },
            "investment_plan": "investment plan content",
        },
    }
    context.trader_handler = lambda _state: {
        "messages": [AIMessage(content="trader plan", id="trader-ai")],
        "trader_investment_plan": "trader investment plan content",
        "sender": "Trader",
    }

    result = StockDagParityWorkflow(context).run()

    assert "600519" in result.state["instrument_context"]
    assert result.state["final_trade_decision"] == "trader investment plan content"
    assert "Risky Analyst" not in result.node_names
    assert "Risk Judge" not in result.node_names
    assert "risk_management_decision" not in result.report["reports"]


def _analyst_handler(report_key: str, content: str):
    def handler(_state):
        return {
            "messages": [AIMessage(content=f"{report_key} done", id=report_key)],
            report_key: content,
        }

    return handler


def test_agent_stock_workflow_has_no_simplified_or_legacy_runtime_calls():
    backend_root = Path(__file__).resolve().parents[7]
    workflow_source_files = [
        *sorted((backend_root / "app/services/research/agent/flow").rglob("*.py")),
        backend_root / "app/services/research/agent/stock.py",
    ]
    for path in workflow_source_files:
        source = path.read_text()
        assert "TradingAgentsGraph(" not in source
        assert ".propagate(" not in source
        assert ".workflow.compile(" not in source

    stock_source = (backend_root / "app/services/research/agent/stock.py").read_text()
    assert "return await run_native_stock_workflow(" not in stock_source
