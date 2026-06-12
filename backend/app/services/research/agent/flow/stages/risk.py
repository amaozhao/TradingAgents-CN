from __future__ import annotations

from typing import Any

from trader.agents import (
    create_neutral_debator,
    create_risky_debator,
    create_safe_debator,
)

from ..graph import StockDagParityPlan
from ..state import apply_node_update
from .conditions import WorkflowConditionAdapter
from .decision import RiskDecisionRunner


class RiskDebateRunner:
    def __init__(
        self,
        context: Any,
        *,
        recorder: Any | None = None,
        handlers: dict[str, Any] | None = None,
        condition_adapter: WorkflowConditionAdapter | None = None,
        decision_runner: RiskDecisionRunner | None = None,
    ):
        self.context = context
        self.recorder = recorder
        self.handlers = handlers or {
            "Risky Analyst": create_risky_debator(context.quick_llm),
            "Safe Analyst": create_safe_debator(context.quick_llm),
            "Neutral Analyst": create_neutral_debator(context.quick_llm),
        }
        self.condition_adapter = condition_adapter or WorkflowConditionAdapter(
            context.conditional_logic
        )
        self.decision_runner = decision_runner

    def run_after_trader(
        self,
        state: dict[str, Any],
        plan: StockDagParityPlan,
    ) -> str:
        if not plan.include_risk:
            state["final_trade_decision"] = state.get("trader_investment_plan", "")
            self._record_edge("Trader", "END")
            return "END"
        self._record_edge("Trader", "Risky Analyst")
        return self.run_until_decision(state, plan)

    def run_until_decision(
        self,
        state: dict[str, Any],
        plan: StockDagParityPlan,
    ) -> str:
        next_node = "Risky Analyst"
        while next_node != "Risk Judge":
            self._run_node(next_node, state)
            next_node = self.condition_adapter.should_continue_risk_analysis(state)
        decision_runner = self.decision_runner or RiskDecisionRunner(
            self.context,
            recorder=self.recorder,
        )
        decision_runner.run_final(state, plan)
        return "END"

    def _run_node(self, node: str, state: dict[str, Any]) -> dict[str, Any]:
        self._record(node)
        update = self.handlers[node](state)
        apply_node_update(state, update)
        return update

    def _record(self, node: str) -> None:
        if self.recorder is None:
            return
        nodes = getattr(self.recorder, "nodes", None)
        if isinstance(nodes, list):
            nodes.append(node)

    def _record_edge(self, source: str, target: str) -> None:
        if self.recorder is None:
            return
        edges = getattr(self.recorder, "edges", None)
        if isinstance(edges, list):
            edges.append((source, target))
