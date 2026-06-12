from __future__ import annotations

from typing import Any, Mapping

from langchain_core.messages import AIMessage, ToolMessage

from trader.agents import (
    create_fundamentals_analyst,
    create_market_analyst,
    create_msg_delete,
    create_news_analyst,
    create_social_media_analyst,
)
from trader.graph.analysts import ANALYST_NODE_SPECS

from ..graph import AnalystPlanNode, StockDagParityPlan
from ..state import apply_node_update
from .conditions import WorkflowConditionAdapter

TOOL_NAMES: dict[str, list[str]] = {
    "market": [
        "get_stock_market_data_unified",
        "get_yfin_data_online",
        "get_stockstats_indicators_report_online",
        "get_yfin_data",
        "get_stockstats_indicators_report",
    ],
    "social": [
        "get_stock_sentiment_unified",
        "get_stock_news_openai",
        "get_reddit_stock_info",
    ],
    "news": [
        "get_stock_news_unified",
        "get_global_news_openai",
        "get_google_news",
        "get_finnhub_news",
        "get_reddit_news",
    ],
    "fundamentals": [
        "get_stock_fundamentals_unified",
        "get_finnhub_company_insider_sentiment",
        "get_finnhub_company_insider_transactions",
        "get_simfin_balance_sheet",
        "get_simfin_cashflow",
        "get_simfin_income_stmt",
        "get_china_stock_data",
        "get_china_fundamentals",
    ],
}


class ToolInventory:
    def __init__(self, toolkit: Any):
        self._tools = {
            key: [getattr(toolkit, name) for name in names]
            for key, names in TOOL_NAMES.items()
        }

    def tools(self, key: str) -> list[Any]:
        try:
            return self._tools[key]
        except KeyError as exc:
            raise ValueError(f"unknown analyst tool group: {key}") from exc

    def tool_names(self, key: str) -> list[str]:
        return [_tool_name(tool) for tool in self.tools(key)]

    def tool_by_name(self, key: str, name: str) -> Any:
        for tool in self.tools(key):
            if _tool_name(tool) == name:
                return tool
        raise ValueError(f"tool {name!r} is not available for {key!r}")


class ToolRunner:
    def __init__(self, inventory: ToolInventory):
        self.inventory = inventory

    def run_tools(
        self,
        key: str,
        state: Mapping[str, Any],
    ) -> dict[str, list[ToolMessage]]:
        message = _last_ai_message(state)
        tool_messages: list[ToolMessage] = []
        for tool_call in message.tool_calls:
            name = str(tool_call["name"])
            args = dict(tool_call.get("args") or {})
            tool = self.inventory.tool_by_name(key, name)
            result = _invoke_tool(tool, args)
            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    name=name,
                    tool_call_id=str(tool_call["id"]),
                )
            )
        return {"messages": tool_messages}


class AnalystStageRunner:
    def __init__(
        self,
        context: Any,
        *,
        recorder: Any | None = None,
        agent_handlers: dict[str, Any] | None = None,
        tool_runner: ToolRunner | None = None,
        clear_handler: Any | None = None,
        condition_adapter: WorkflowConditionAdapter | None = None,
    ):
        self.context = context
        self.recorder = recorder
        self.agent_handlers = agent_handlers or _build_agent_handlers(context)
        self.tool_runner = tool_runner or ToolRunner(ToolInventory(context.toolkit))
        self.clear_handler = clear_handler or create_msg_delete()
        self.condition_adapter = condition_adapter or WorkflowConditionAdapter(
            context.conditional_logic
        )

    def run_agent(self, key: str, state: dict[str, Any]) -> dict[str, Any]:
        spec = _spec_for_key(key)
        self._record(spec.agent_node)
        update = self.agent_handlers[key](state)
        apply_node_update(state, update)
        return update

    def run_tools(self, key: str, state: dict[str, Any]) -> dict[str, Any]:
        spec = _spec_for_key(key)
        self._record(spec.tool_node)
        update = self.tool_runner.run_tools(key, state)
        apply_node_update(state, update)
        return update

    def clear_messages(self, key: str, state: dict[str, Any]) -> dict[str, Any]:
        spec = _spec_for_key(key)
        self._record(spec.clear_node)
        update = self.clear_handler(state)
        apply_node_update(state, update)
        return update

    def run_selected_analysts(
        self,
        state: dict[str, Any],
        plan: StockDagParityPlan,
    ) -> str:
        for spec in plan.analyst_specs:
            self._run_single_analyst(spec, state)
        return "Bull Researcher"

    def _run_single_analyst(
        self,
        spec: AnalystPlanNode,
        state: dict[str, Any],
    ) -> None:
        while True:
            self.run_agent(spec.key, state)
            next_node = _condition_method(self.condition_adapter, spec.key)(state)
            if next_node == spec.tool_node:
                self.run_tools(spec.key, state)
                continue
            if next_node == spec.clear_node:
                self.clear_messages(spec.key, state)
                return
            raise ValueError(
                f"unexpected next node {next_node!r} for analyst {spec.key!r}"
            )

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


def _last_ai_message(state: Mapping[str, Any]) -> AIMessage:
    messages = state.get("messages") or []
    if not messages or not isinstance(messages[-1], AIMessage):
        raise ValueError("last state message must be an AIMessage with tool calls")
    return messages[-1]


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", ""))


def _invoke_tool(tool: Any, args: dict[str, Any]) -> Any:
    invoke = getattr(tool, "invoke", None)
    if callable(invoke):
        return invoke(args)
    return tool(**args)


def _build_agent_handlers(context: Any) -> dict[str, Any]:
    return {
        "market": create_market_analyst(context.quick_llm, context.toolkit),
        "social": create_social_media_analyst(context.quick_llm, context.toolkit),
        "news": create_news_analyst(context.quick_llm, context.toolkit),
        "fundamentals": create_fundamentals_analyst(
            context.quick_llm,
            context.toolkit,
        ),
    }


def _spec_for_key(key: str) -> AnalystPlanNode:
    spec = ANALYST_NODE_SPECS[key]
    return AnalystPlanNode(
        key=spec.key,
        agent_node=spec.agent_node,
        clear_node=spec.clear_node,
        tool_node=spec.tool_node,
        report_key=spec.report_key,
    )


def _condition_method(adapter: WorkflowConditionAdapter, key: str) -> Any:
    if key == "social":
        return adapter.should_continue_social
    return getattr(adapter, f"should_continue_{key}")
