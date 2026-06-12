from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from trader.agents.utils.instruments import build_instrument_context
from trader.flows.utils import safe_ticker_component

from .checkpoint import UnsupportedCheckpointError
from .events import StockWorkflowEventEmitter, build_stock_workflow_stage_events
from .graph import DEFAULT_ANALYSTS, StockDagParityPlan, build_stock_dag_parity_plan
from .stages.analysts import AnalystStageRunner
from .stages.decision import RiskDecisionRunner
from .stages.reports import build_stock_workflow_report
from .stages.research import ResearchDebateRunner
from .stages.risk import RiskDebateRunner
from .stages.trader import TraderDecisionRunner
from .state import create_stock_initial_state, validate_final_state

WorkflowExecutor = Callable[[], tuple[dict[str, Any], dict[str, float], float]]
NodeRecordCallback = Callable[[str, str | None], None]


@dataclass(frozen=True)
class StockDagParityWorkflowResult:
    state: dict[str, Any]
    decision: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)
    node_events: list[dict[str, Any]] = field(default_factory=list)
    stage_events: list[dict[str, Any]] = field(default_factory=list)
    node_names: list[str] = field(default_factory=list)
    task_id: str | None = None
    status: str = "completed"
    source: str = "agent_workflow_dag_parity"


class StockDagParityWorkflow:
    def __init__(
        self,
        context: Any,
        *,
        executor: WorkflowExecutor | None = None,
        events: list[dict[str, Any]] | None = None,
        on_node_record: NodeRecordCallback | None = None,
    ):
        self.context = context
        self.executor = executor
        self.events = events or []
        self.on_node_record = on_node_record

    def run(self) -> StockDagParityWorkflowResult:
        config = getattr(self.context, "config", {}) or {}
        if config.get("checkpoint_enabled"):
            raise UnsupportedCheckpointError(
                "Agent stock workflow checkpoint resume is not implemented yet"
            )

        memory_log = getattr(self.context, "memory_log", None)
        _resolve_pending_entries(self.context, memory_log)
        past_context = ""
        if memory_log is not None and hasattr(memory_log, "get_past_context"):
            past_context = memory_log.get_past_context(self.context.symbol)

        recorder = _WorkflowRecorder(on_record=self.on_node_record)
        plan = _plan_for_context(self.context)
        if self.executor is None:
            state, node_timings, total_elapsed = self._run_default_executor(
                plan,
                recorder,
                past_context=past_context or "",
            )
        else:
            state, node_timings, total_elapsed = self.executor()
        state["performance_metrics"] = build_performance_metrics(
            node_timings,
            total_elapsed,
            config,
        )
        validate_final_state(state)
        self.context.curr_state = state
        _log_state(self.context, state)

        if memory_log is not None:
            memory_log.store_decision(
                ticker=self.context.symbol,
                trade_date=str(self.context.trade_date),
                final_trade_decision=state["final_trade_decision"],
            )

        decision = self.context.signal_processor.process_signal(
            state["final_trade_decision"],
            self.context.symbol,
        )
        decision["model_info"] = _model_info(getattr(self.context, "deep_llm", None))
        report = build_stock_workflow_report(
            self.context,
            state,
            decision,
            execution_time=total_elapsed,
        )
        node_events = _node_events_for_run(self.context, report, recorder.nodes)
        stage_events = build_stock_workflow_stage_events(
            plan=plan,
            reports=report.get("reports", {}),
            task_id=str(getattr(self.context, "task_id", "") or ""),
            analysis_id=str(report.get("analysis_id") or ""),
            attempt_id=getattr(self.context, "attempt_id", None),
        )

        return StockDagParityWorkflowResult(
            state=state,
            decision=decision,
            events=[*self.events, *node_events, *stage_events],
            report=report,
            node_events=node_events,
            stage_events=stage_events,
            node_names=list(recorder.nodes),
            task_id=getattr(self.context, "task_id", None),
        )

    def _run_default_executor(
        self,
        plan: StockDagParityPlan,
        recorder: Any,
        *,
        past_context: str,
    ) -> tuple[dict[str, Any], dict[str, float], float]:
        started = time.perf_counter()
        state = create_stock_initial_state(
            self.context.symbol,
            str(self.context.trade_date),
            asset_type=getattr(self.context, "asset_type", "stock"),
            past_context=past_context,
            instrument_context=_resolve_instrument_context(self.context),
        )
        AnalystStageRunner(
            self.context,
            recorder=recorder,
            agent_handlers=getattr(self.context, "agent_handlers", None),
            tool_runner=getattr(self.context, "tool_runner", None),
            clear_handler=getattr(self.context, "clear_handler", None),
        ).run_selected_analysts(state, plan)
        ResearchDebateRunner(
            self.context,
            recorder=recorder,
            handlers=getattr(self.context, "research_handlers", None),
        ).run_until_manager(state)
        TraderDecisionRunner(
            self.context,
            recorder=recorder,
            handler=getattr(self.context, "trader_handler", None),
        ).run_trader(state)
        decision_runner = (
            RiskDecisionRunner(
                self.context,
                recorder=recorder,
                handlers=getattr(self.context, "risk_decision_handlers", None),
            )
            if plan.include_risk
            else None
        )
        RiskDebateRunner(
            self.context,
            recorder=recorder,
            handlers=getattr(self.context, "risk_handlers", None),
            decision_runner=decision_runner,
        ).run_after_trader(state, plan)
        recorder.record("END")
        total_elapsed = time.perf_counter() - started
        return state, {node: 0.0 for node in recorder.nodes}, total_elapsed


def build_performance_metrics(
    node_timings: dict[str, float],
    total_elapsed: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    buckets = {
        "analyst_team": {},
        "tool_calls": {},
        "message_clearing": {},
        "research_team": {},
        "trader_team": {},
        "risk_management_team": {},
        "other": {},
    }
    for node_name, elapsed in node_timings.items():
        buckets[_bucket_for_node(node_name)][node_name] = elapsed

    return {
        "total_time": round(total_elapsed, 2),
        "total_time_minutes": round(total_elapsed / 60, 2),
        "node_count": len(node_timings),
        "average_node_time": round(
            sum(node_timings.values()) / len(node_timings) if node_timings else 0,
            2,
        ),
        "node_timings": {k: round(v, 2) for k, v in node_timings.items()},
        "category_timings": {
            name: {
                "nodes": {k: round(v, 2) for k, v in values.items()},
                "total": round(sum(values.values()), 2),
                "percentage": round(sum(values.values()) / total_elapsed * 100, 1)
                if total_elapsed > 0
                else 0,
            }
            for name, values in buckets.items()
        },
        "llm_config": {
            "provider": config.get("llm_provider", "unknown"),
            "deep_think_model": config.get("deep_think_llm", "unknown"),
            "quick_think_model": config.get("quick_think_llm", "unknown"),
        },
    }


def _bucket_for_node(node_name: str) -> str:
    if (
        "Risky" in node_name
        or "Safe" in node_name
        or "Neutral" in node_name
        or "Risk Judge" in node_name
        or "Portfolio Manager" in node_name
    ):
        return "risk_management_team"
    if "Analyst" in node_name:
        return "analyst_team"
    if node_name.startswith("tools_"):
        return "tool_calls"
    if node_name.startswith("Msg Clear"):
        return "message_clearing"
    if "Researcher" in node_name or "Research Manager" in node_name:
        return "research_team"
    if "Trader" in node_name:
        return "trader_team"
    return "other"


def _model_info(model: Any) -> str:
    if model is None:
        return "Unknown"
    model_name = getattr(model, "model_name", None)
    if model_name:
        return f"{model.__class__.__name__}:{model_name}"
    return model.__class__.__name__


def _resolve_instrument_context(context: Any) -> str:
    symbol = str(getattr(context, "symbol", ""))
    asset_type = str(getattr(context, "asset_type", "stock") or "stock")
    return build_instrument_context(symbol, asset_type=asset_type)


def _resolve_pending_entries(context: Any, memory_log: Any) -> None:
    if memory_log is None or not hasattr(memory_log, "get_pending_entries"):
        return
    if not hasattr(memory_log, "batch_update_with_outcomes"):
        return

    ticker = str(getattr(context, "symbol", ""))
    pending = [
        entry
        for entry in memory_log.get_pending_entries()
        if str(entry.get("ticker") or "") == ticker
    ]
    if not pending:
        return

    benchmark = _resolve_benchmark(context, ticker)
    reflector = getattr(context, "reflector", None)
    updates: list[dict[str, Any]] = []
    for entry in pending:
        trade_date = str(entry.get("date") or "")
        raw_return, alpha_return, holding_days = _fetch_pending_returns(
            context,
            ticker,
            trade_date,
            benchmark,
        )
        if raw_return is None or alpha_return is None:
            continue
        reflection = ""
        if reflector is not None and hasattr(reflector, "reflect_on_final_decision"):
            reflection = reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw_return,
                alpha_return=alpha_return,
                benchmark_name=benchmark,
            )
        updates.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "raw_return": raw_return,
                "alpha_return": alpha_return,
                "holding_days": holding_days,
                "reflection": reflection,
            }
        )

    if updates:
        memory_log.batch_update_with_outcomes(updates)


def _resolve_benchmark(context: Any, ticker: str) -> str:
    config = getattr(context, "config", {}) or {}
    explicit = config.get("benchmark_ticker")
    if explicit:
        return str(explicit)
    benchmark_map = config.get("benchmark_map", {})
    if not isinstance(benchmark_map, dict):
        benchmark_map = {}
    ticker_upper = str(ticker).upper()
    for suffix, benchmark in benchmark_map.items():
        if suffix and ticker_upper.endswith(str(suffix).upper()):
            return str(benchmark)
    return str(benchmark_map.get("", "SPY"))


def _fetch_pending_returns(
    _context: Any,
    ticker: str,
    trade_date: str,
    benchmark: str,
    holding_days: int = 5,
) -> tuple[float | None, float | None, int | None]:
    try:
        yfinance = __import__("yfinance")
        start = datetime.strptime(str(trade_date), "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 7)
        stock = yfinance.Ticker(ticker).history(
            start=str(trade_date),
            end=end.strftime("%Y-%m-%d"),
        )
        bench = yfinance.Ticker(benchmark).history(
            start=str(trade_date),
            end=end.strftime("%Y-%m-%d"),
        )
        if len(stock) < 2 or len(bench) < 2:
            return None, None, None
        actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
        raw_return = float(
            (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
            / stock["Close"].iloc[0]
        )
        benchmark_return = float(
            (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
            / bench["Close"].iloc[0]
        )
        return raw_return, raw_return - benchmark_return, actual_days
    except Exception:
        return None, None, None


def _log_state(context: Any, state: dict[str, Any]) -> None:
    trade_date = str(getattr(context, "trade_date", state.get("trade_date", "")))
    payload = _state_log_payload(state)
    log_states = dict(getattr(context, "log_states_dict", {}) or {})
    log_states[trade_date] = payload
    setattr(context, "log_states_dict", log_states)

    config = getattr(context, "config", {}) or {}
    base_dir = Path(config.get("state_log_dir") or "eval_results")
    safe_ticker = safe_ticker_component(str(getattr(context, "symbol", "")))
    directory = base_dir / safe_ticker / "TradingAgentsStrategy_logs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "full_states_log.json").write_text(
        json.dumps(log_states, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def _state_log_payload(state: dict[str, Any]) -> dict[str, Any]:
    investment = state.get("investment_debate_state") or {}
    risk = state.get("risk_debate_state") or {}
    return {
        "company_of_interest": state.get("company_of_interest", ""),
        "trade_date": state.get("trade_date", ""),
        "market_report": state.get("market_report", ""),
        "sentiment_report": state.get("sentiment_report", ""),
        "news_report": state.get("news_report", ""),
        "fundamentals_report": state.get("fundamentals_report", ""),
        "investment_debate_state": {
            "bull_history": investment.get("bull_history", ""),
            "bear_history": investment.get("bear_history", ""),
            "history": investment.get("history", ""),
            "current_response": investment.get("current_response", ""),
            "judge_decision": investment.get("judge_decision", ""),
        },
        "trader_investment_decision": state.get("trader_investment_plan", ""),
        "risk_debate_state": {
            "risky_history": risk.get("risky_history", ""),
            "safe_history": risk.get("safe_history", ""),
            "neutral_history": risk.get("neutral_history", ""),
            "history": risk.get("history", ""),
            "judge_decision": risk.get("judge_decision", ""),
        },
        "investment_plan": state.get("investment_plan", ""),
        "final_trade_decision": state.get("final_trade_decision", ""),
    }


class _WorkflowRecorder:
    def __init__(self, *, on_record: NodeRecordCallback | None = None):
        self.nodes: list[str] = []
        self.edges: list[tuple[str, str]] = []
        self.on_record = on_record

    def record(self, node: str) -> None:
        previous = self.nodes[-1] if self.nodes else None
        self.nodes.append(node)
        if self.on_record:
            self.on_record(node, previous)


def _plan_for_context(context: Any) -> StockDagParityPlan:
    config = getattr(context, "config", {}) or {}
    return build_stock_dag_parity_plan(
        getattr(context, "selected_analysts", None) or list(DEFAULT_ANALYSTS),
        str(config.get("final_decision_engine") or "risk_manager"),
        include_risk=bool(config.get("include_risk", True)),
    )


def _node_events_for_run(
    context: Any,
    report: dict[str, Any],
    node_names: list[str],
) -> list[dict[str, Any]]:
    emitter = StockWorkflowEventEmitter(
        task_id=str(getattr(context, "task_id", "") or ""),
        analysis_id=str(report.get("analysis_id") or ""),
        attempt_id=getattr(context, "attempt_id", None),
    )
    previous = None
    events = []
    for node in node_names:
        events.append(
            emitter.node_event(
                node=node,
                status="completed",
                edge_from=previous,
                edge_to=node,
            )
        )
        previous = node
    return events
