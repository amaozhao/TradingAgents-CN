from __future__ import annotations

from typing import Any

from trader.agents import create_trader

from ..state import apply_node_update


class TraderDecisionRunner:
    def __init__(
        self,
        context: Any,
        *,
        recorder: Any | None = None,
        handler: Any | None = None,
    ):
        self.context = context
        self.recorder = recorder
        self.handler = handler or create_trader(context.quick_llm, context.trader_memory)

    def run_trader(self, state: dict[str, Any]) -> dict[str, Any]:
        self._record("Trader")
        update = self.handler(state)
        apply_node_update(state, update)
        return update

    def _record(self, node: str) -> None:
        if self.recorder is None:
            return
        nodes = getattr(self.recorder, "nodes", None)
        if isinstance(nodes, list):
            nodes.append(node)
