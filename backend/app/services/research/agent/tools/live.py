from __future__ import annotations

from typing import Any

from app.services.research.agent.live import LiveSafetyService

from ..context import ToolExecutionContext
from ..permissions import LIVE_MANDATE_PROPOSE, LIVE_READ
from ..registry import ResearchTool


async def _connections(context: ToolExecutionContext, _payload: dict[str, Any]) -> dict[str, Any]:
    status = await LiveSafetyService().get_status(context.principal)
    return {
        "tool": "trading_connections",
        "status": "completed",
        "profiles": [
            {
                "broker": item["auth"]["broker"],
                "oauth_token_present": item["auth"]["oauth_token_present"],
                "is_live_broker": item["auth"]["is_live_broker"],
                "halted": item["halted"],
            }
            for item in status["brokers"]
        ],
    }


async def _check(context: ToolExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
    broker = str(payload.get("broker") or "") or None
    snapshot = await LiveSafetyService().connector_snapshot(context.principal, broker)
    return {"tool": "trading_check", **snapshot}


async def _select_connection(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    broker = str(payload.get("broker") or "paper")
    selected = await LiveSafetyService().select_connection(
        principal=context.principal,
        broker=broker,
        session_id=str(context.session_id) if context.session_id else None,
    )
    return {"tool": "trading_select_connection", "status": "completed", **selected}


async def _empty_readonly(
    context: ToolExecutionContext, payload: dict[str, Any], *, tool_name: str
) -> dict[str, Any]:
    snapshot = await LiveSafetyService().connector_snapshot(
        context.principal, str(payload.get("broker") or "") or None
    )
    return {
        "tool": tool_name,
        "status": snapshot["status"],
        "read_only": True,
        "live_trading_enabled": False,
        "broker": snapshot["broker"],
        "data": [],
        "reason": "No live broker connector is configured in the current project runtime.",
    }


async def _propose_mandate(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    proposal = await LiveSafetyService().propose_mandate(
        principal=context.principal,
        session_id=str(context.session_id) if context.session_id else None,
        broker=str(payload.get("broker") or "paper"),
        account_ref=str(payload.get("account_ref") or "research-only"),
        constraints=dict(payload.get("constraints") or {}),
    )
    return {"tool": "propose_mandate_profiles", "status": "proposed", "proposal": proposal}


def live_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="trading_connections",
            description="List current-project trading connector profiles without exposing secrets.",
            permission=LIVE_READ,
            schema={"type": "object", "additionalProperties": True},
            handler=_connections,
        ),
        ResearchTool(
            name="trading_check",
            description="Check selected connector readiness in read-only mode.",
            permission=LIVE_READ,
            schema={"type": "object", "properties": {"broker": {"type": "string"}}},
            handler=_check,
        ),
        ResearchTool(
            name="trading_select_connection",
            description="Select the current read-only connector profile without enabling order mutation.",
            permission=LIVE_READ,
            schema={"type": "object", "properties": {"broker": {"type": "string"}}},
            handler=_select_connection,
        ),
        *[
            ResearchTool(
                name=name,
                description=f"Read-only live connector {name.removeprefix('trading_')} snapshot.",
                permission=LIVE_READ,
                schema={"type": "object", "properties": {"broker": {"type": "string"}}},
                handler=lambda context, payload, tool_name=name: _empty_readonly(
                    context, payload, tool_name=tool_name
                ),
            )
            for name in (
                "trading_account",
                "trading_positions",
                "trading_orders",
                "trading_quote",
                "trading_history",
            )
        ],
        ResearchTool(
            name="propose_mandate_profiles",
            description="Propose live mandate profiles; does not commit or enable trading.",
            permission=LIVE_MANDATE_PROPOSE,
            schema={
                "type": "object",
                "properties": {
                    "broker": {"type": "string"},
                    "account_ref": {"type": "string"},
                    "constraints": {"type": "object"},
                },
            },
            handler=_propose_mandate,
        ),
    ]
