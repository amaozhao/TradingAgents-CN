from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from trader.graph.analysts import (
    ANALYST_NODE_SPECS,
    build_analyst_execution_plan,
)

DEFAULT_ANALYSTS = ("market", "social", "news", "fundamentals")
START_NODE = "START"
END_NODE = "END"


@dataclass(frozen=True)
class AnalystPlanNode:
    key: str
    agent_node: str
    clear_node: str
    tool_node: str
    report_key: str


@dataclass(frozen=True)
class ConditionalEdge:
    source: str
    targets: list[str] = field(default_factory=list)
    target_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StockDagParityPlan:
    analyst_specs: list[AnalystPlanNode]
    nodes: list[str]
    normal_edges: list[tuple[str, str]]
    conditional_edges: dict[str, ConditionalEdge]
    resolved_conditional_targets: list[tuple[str, str]]
    first_node: str
    final_risk_node: str
    skipped_nodes: set[str]
    stage_status_overrides: dict[str, str]
    analyst_concurrency_limit: int
    include_risk: bool


def build_stock_dag_parity_plan(
    selected_analysts: Iterable[str] | None,
    final_decision_engine: str,
    analyst_concurrency_limit: int = 1,
    include_risk: bool = True,
) -> StockDagParityPlan:
    analyst_keys = tuple(selected_analysts or DEFAULT_ANALYSTS)
    analyst_plan = build_analyst_execution_plan(
        analyst_keys,
        concurrency_limit=analyst_concurrency_limit,
    )
    analyst_specs = [
        AnalystPlanNode(
            key=spec.key,
            agent_node=spec.agent_node,
            clear_node=spec.clear_node,
            tool_node=spec.tool_node,
            report_key=spec.report_key,
        )
        for spec in analyst_plan.specs
    ]

    final_risk_node = _resolve_final_risk_node(final_decision_engine)
    normal_edges = _build_analyst_normal_edges(analyst_specs)
    conditional_edges = _build_analyst_conditional_edges(analyst_specs)

    conditional_edges.update(
        {
            "Bull Researcher": ConditionalEdge(
                source="Bull Researcher",
                target_map={
                    "Bear Researcher": "Bear Researcher",
                    "Research Manager": "Research Manager",
                },
            ),
            "Bear Researcher": ConditionalEdge(
                source="Bear Researcher",
                target_map={
                    "Bull Researcher": "Bull Researcher",
                    "Research Manager": "Research Manager",
                },
            ),
        }
    )
    normal_edges.append(("Research Manager", "Trader"))

    skipped_nodes: set[str] = set()
    stage_status_overrides: dict[str, str] = {}
    if include_risk:
        normal_edges.extend(
            [
                ("Trader", "Risky Analyst"),
                (final_risk_node, END_NODE),
            ]
        )
        conditional_edges.update(_build_risk_conditional_edges(final_risk_node))
    else:
        normal_edges.append(("Trader", END_NODE))
        skipped_nodes.update(
            {
                "Risky Analyst",
                "Safe Analyst",
                "Neutral Analyst",
                "Risk Judge",
                "Portfolio Manager",
            }
        )
        stage_status_overrides.update(
            {
                "risk_debate": "skipped",
                "final_risk_decision": "skipped",
            }
        )

    return StockDagParityPlan(
        analyst_specs=analyst_specs,
        nodes=_build_nodes(analyst_specs, final_risk_node, include_risk),
        normal_edges=normal_edges,
        conditional_edges=conditional_edges,
        resolved_conditional_targets=_resolve_conditional_targets(conditional_edges),
        first_node=analyst_specs[0].agent_node,
        final_risk_node=final_risk_node,
        skipped_nodes=skipped_nodes,
        stage_status_overrides=stage_status_overrides,
        analyst_concurrency_limit=analyst_plan.concurrency_limit,
        include_risk=include_risk,
    )


def _resolve_final_risk_node(final_decision_engine: str) -> str:
    if final_decision_engine == "portfolio_manager":
        return "Portfolio Manager"
    if final_decision_engine == "risk_manager":
        return "Risk Judge"
    raise ValueError(f"unknown final decision engine: {final_decision_engine}")


def _build_nodes(
    analyst_specs: list[AnalystPlanNode],
    final_risk_node: str,
    include_risk: bool,
) -> list[str]:
    nodes: list[str] = []
    for spec in analyst_specs:
        nodes.extend([spec.agent_node, spec.tool_node, spec.clear_node])

    nodes.extend(["Bull Researcher", "Bear Researcher", "Research Manager", "Trader"])
    if include_risk:
        nodes.extend(["Risky Analyst", "Safe Analyst", "Neutral Analyst", final_risk_node])
    nodes.append(END_NODE)
    return nodes


def _build_analyst_normal_edges(
    analyst_specs: list[AnalystPlanNode],
) -> list[tuple[str, str]]:
    normal_edges: list[tuple[str, str]] = [(START_NODE, analyst_specs[0].agent_node)]
    for index, spec in enumerate(analyst_specs):
        normal_edges.append((spec.tool_node, spec.agent_node))
        next_node = (
            analyst_specs[index + 1].agent_node
            if index < len(analyst_specs) - 1
            else "Bull Researcher"
        )
        normal_edges.append((spec.clear_node, next_node))
    return normal_edges


def _build_analyst_conditional_edges(
    analyst_specs: list[AnalystPlanNode],
) -> dict[str, ConditionalEdge]:
    return {
        spec.agent_node: ConditionalEdge(
            source=spec.agent_node,
            targets=[spec.tool_node, spec.clear_node],
        )
        for spec in analyst_specs
        if spec.key in ANALYST_NODE_SPECS
    }


def _build_risk_conditional_edges(final_risk_node: str) -> dict[str, ConditionalEdge]:
    return {
        "Risky Analyst": ConditionalEdge(
            source="Risky Analyst",
            target_map={
                "Safe Analyst": "Safe Analyst",
                "Risk Judge": final_risk_node,
            },
        ),
        "Safe Analyst": ConditionalEdge(
            source="Safe Analyst",
            target_map={
                "Neutral Analyst": "Neutral Analyst",
                "Risk Judge": final_risk_node,
            },
        ),
        "Neutral Analyst": ConditionalEdge(
            source="Neutral Analyst",
            target_map={
                "Risky Analyst": "Risky Analyst",
                "Risk Judge": final_risk_node,
            },
        ),
    }


def _resolve_conditional_targets(
    conditional_edges: dict[str, ConditionalEdge],
) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for source, edge in conditional_edges.items():
        targets.extend((source, target) for target in edge.targets)
        targets.extend((source, target) for target in edge.target_map.values())
    return targets
