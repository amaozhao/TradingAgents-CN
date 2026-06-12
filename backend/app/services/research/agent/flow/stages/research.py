from __future__ import annotations

from typing import Any

from trader.agents import (
    create_bear_researcher,
    create_bull_researcher,
    create_research_manager,
)

from ..state import apply_node_update
from .conditions import WorkflowConditionAdapter


class ResearchDebateRunner:
    def __init__(
        self,
        context: Any,
        *,
        recorder: Any | None = None,
        handlers: dict[str, Any] | None = None,
        condition_adapter: WorkflowConditionAdapter | None = None,
    ):
        self.context = context
        self.recorder = recorder
        self.handlers = handlers or {
            "Bull Researcher": create_bull_researcher(
                context.quick_llm,
                context.bull_memory,
            ),
            "Bear Researcher": create_bear_researcher(
                context.quick_llm,
                context.bear_memory,
            ),
            "Research Manager": create_research_manager(
                context.deep_llm,
                context.invest_judge_memory,
            ),
        }
        self.condition_adapter = condition_adapter or WorkflowConditionAdapter(
            context.conditional_logic
        )

    def run_bull(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._run_node("Bull Researcher", state)

    def run_bear(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._run_node("Bear Researcher", state)

    def run_manager(self, state: dict[str, Any]) -> dict[str, Any]:
        return self._run_node("Research Manager", state)

    def run_until_manager(self, state: dict[str, Any]) -> str:
        self.run_bull(state)
        next_node = self.condition_adapter.should_continue_debate(state)
        while next_node != "Research Manager":
            if next_node == "Bear Researcher":
                self.run_bear(state)
            elif next_node == "Bull Researcher":
                self.run_bull(state)
            else:
                raise ValueError(f"unexpected research debate node: {next_node!r}")
            next_node = self.condition_adapter.should_continue_debate(state)
        self.run_manager(state)
        return "Trader"

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
            return
        record = getattr(self.recorder, "record", None)
        if callable(record):
            record(node)
