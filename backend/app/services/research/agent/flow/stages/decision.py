from __future__ import annotations

from typing import Any

from trader.agents import create_portfolio_manager, create_risk_manager

from ..graph import StockDagParityPlan
from ..state import apply_node_update


class RiskDecisionRunner:
    def __init__(
        self,
        context: Any,
        *,
        recorder: Any | None = None,
        handlers: dict[str, Any] | None = None,
    ):
        self.context = context
        self.recorder = recorder
        self.handlers = handlers or {
            "Risk Judge": create_risk_manager(
                context.deep_llm,
                context.risk_manager_memory,
            ),
            "Portfolio Manager": create_portfolio_manager(context.deep_llm),
        }

    def run_final(
        self,
        state: dict[str, Any],
        plan: StockDagParityPlan,
    ) -> dict[str, Any]:
        node = plan.final_risk_node
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
