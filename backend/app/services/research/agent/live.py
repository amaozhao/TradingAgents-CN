from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .events import ResearchEventService
from .models import now_utc
from .permissions import (
    LIVE_HALT,
    LIVE_MANDATE_COMMIT,
    LIVE_RUNNER_CONTROL,
)


DEFAULT_BROKER = "paper"


class LivePermissionError(PermissionError):
    pass


class LiveSafetyError(RuntimeError):
    pass


class LiveSafetyService:
    def __init__(self, event_service: ResearchEventService | None = None):
        self.event_service = event_service or ResearchEventService()

    def _state(self):
        return get_postgres_db().research_live_state

    def _audit(self):
        return get_postgres_db().research_live_audit

    async def get_status(self, principal: ResearchPrincipal) -> dict[str, Any]:
        state = await self._get_user_state(principal.user_id)
        broker = str(state.get("broker") or DEFAULT_BROKER)
        mandate = state.get("mandate")
        runner = state.get("runner")
        halted = bool(state.get("global_halted") or state.get("broker_halted"))
        return {
            "global_halted": bool(state.get("global_halted")),
            "brokers": [
                {
                    "auth": {
                        "broker": broker,
                        "oauth_token_present": bool(state.get("oauth_token_present")),
                        "is_live_broker": False,
                    },
                    "mandate": mandate,
                    "runner": runner,
                    "halted": halted,
                }
            ],
        }

    async def propose_mandate(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str | None,
        broker: str = DEFAULT_BROKER,
        account_ref: str = "research-only",
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "broker": broker,
            "account_ref": account_ref,
            "constraints": dict(constraints or {}),
            "status": "proposed",
            "created_at": now_utc(),
        }
        await self._audit_action(
            principal=principal,
            action="mandate.proposed",
            session_id=session_id,
            payload=proposal,
            event_type="mandate.proposed",
        )
        return proposal

    async def commit_mandate(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str | None,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        self._require(principal, LIVE_MANDATE_COMMIT)
        broker = str(proposal.get("broker") or DEFAULT_BROKER)
        mandate = {
            "broker": broker,
            "account_ref": str(proposal.get("account_ref") or "research-only"),
            "expires_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "expired": False,
            "constraints": dict(proposal.get("constraints") or {}),
        }
        state = await self._get_user_state(principal.user_id)
        await self._upsert_state(
            principal.user_id,
            {
                **state,
                "broker": broker,
                "mandate": mandate,
                "updated_at": now_utc(),
            },
        )
        await self._audit_action(
            principal=principal,
            action="mandate.committed",
            session_id=session_id,
            payload=mandate,
            event_type="mandate.committed",
        )
        return mandate

    async def halt(
        self,
        *,
        principal: ResearchPrincipal,
        reason: str,
        broker: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._require(principal, LIVE_HALT)
        state = await self._get_user_state(principal.user_id)
        update = {
            **state,
            "broker": broker or state.get("broker") or DEFAULT_BROKER,
            "global_halted": broker is None,
            "broker_halted": broker is not None,
            "halt_reason": reason,
            "updated_at": now_utc(),
        }
        await self._upsert_state(principal.user_id, update)
        payload = {"halted": True, "broker": broker, "reason": reason}
        await self._audit_action(
            principal=principal,
            action="live.halted",
            session_id=session_id,
            payload=payload,
            event_type="live.halted",
        )
        return payload

    async def resume(
        self,
        *,
        principal: ResearchPrincipal,
        reason: str,
        broker: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._require(principal, LIVE_HALT)
        state = await self._get_user_state(principal.user_id)
        update = {
            **state,
            "broker": broker or state.get("broker") or DEFAULT_BROKER,
            "global_halted": False if broker is None else state.get("global_halted", False),
            "broker_halted": False,
            "resume_reason": reason,
            "updated_at": now_utc(),
        }
        await self._upsert_state(principal.user_id, update)
        payload = {"resumed": True, "broker": broker, "reason": reason}
        await self._audit_action(
            principal=principal,
            action="live.resumed",
            session_id=session_id,
            payload=payload,
            event_type="live.resumed",
        )
        return payload

    async def authorize(
        self,
        *,
        principal: ResearchPrincipal,
        broker: str = DEFAULT_BROKER,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._require(principal, LIVE_RUNNER_CONTROL)
        state = await self._get_user_state(principal.user_id)
        await self._upsert_state(
            principal.user_id,
            {
                **state,
                "broker": broker,
                "oauth_token_present": True,
                "updated_at": now_utc(),
            },
        )
        payload = {"broker": broker, "oauth_token_present": True}
        await self._audit_action(
            principal=principal,
            action="live.authorized",
            session_id=session_id,
            payload=payload,
            event_type="live.action",
        )
        return payload

    async def runner_start(
        self,
        *,
        principal: ResearchPrincipal,
        broker: str = DEFAULT_BROKER,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._require(principal, LIVE_RUNNER_CONTROL)
        state = await self._get_user_state(principal.user_id)
        self._assert_runner_can_start(state)
        runner = {"broker": broker, "alive": True, "last_tick": None, "last_tick_age_seconds": None}
        await self._upsert_state(
            principal.user_id,
            {**state, "broker": broker, "runner": runner, "updated_at": now_utc()},
        )
        await self._audit_action(
            principal=principal,
            action="live.runner.started",
            session_id=session_id,
            payload=runner,
            event_type="live.action",
        )
        return runner

    async def runner_stop(
        self,
        *,
        principal: ResearchPrincipal,
        broker: str = DEFAULT_BROKER,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self._require(principal, LIVE_RUNNER_CONTROL)
        state = await self._get_user_state(principal.user_id)
        runner = {"broker": broker, "alive": False, "last_tick": None, "last_tick_age_seconds": None}
        await self._upsert_state(
            principal.user_id,
            {**state, "broker": broker, "runner": runner, "updated_at": now_utc()},
        )
        await self._audit_action(
            principal=principal,
            action="live.runner.stopped",
            session_id=session_id,
            payload=runner,
            event_type="live.action",
        )
        return runner

    async def connector_snapshot(
        self, principal: ResearchPrincipal, broker: str | None = None
    ) -> dict[str, Any]:
        status = await self.get_status(principal)
        selected = broker or status["brokers"][0]["auth"]["broker"]
        broker_status = next(
            (item for item in status["brokers"] if item["auth"]["broker"] == selected),
            status["brokers"][0],
        )
        return {
            "broker": selected,
            "status": "connected" if broker_status["auth"]["oauth_token_present"] else "config_required",
            "read_only": True,
            "live_trading_enabled": False,
            "details": broker_status,
        }

    async def select_connection(
        self,
        *,
        principal: ResearchPrincipal,
        broker: str = DEFAULT_BROKER,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        state = await self._get_user_state(principal.user_id)
        await self._upsert_state(
            principal.user_id,
            {**state, "broker": broker, "updated_at": now_utc()},
        )
        payload = {"broker": broker, "selected": True, "live_trading_enabled": False}
        await self._audit_action(
            principal=principal,
            action="trading.connection.selected",
            session_id=session_id,
            payload=payload,
            event_type="live.action",
        )
        return payload

    async def _get_user_state(self, user_id: str) -> dict[str, Any]:
        state = await self._state().find_one({"user_id": str(user_id)})
        return dict(state or {"user_id": str(user_id), "global_halted": False})

    async def _upsert_state(self, user_id: str, state: dict[str, Any]) -> None:
        existing = await self._state().find_one({"user_id": str(user_id)})
        document = {"_id": existing.get("_id") if existing else str(uuid.uuid4()), **state, "user_id": str(user_id)}
        if existing:
            await self._state().update_one({"user_id": str(user_id)}, {"$set": document})
        else:
            await self._state().insert_one(document)

    async def _audit_action(
        self,
        *,
        principal: ResearchPrincipal,
        action: str,
        session_id: str | None,
        payload: dict[str, Any],
        event_type: str,
    ) -> None:
        audit = {
            "_id": str(uuid.uuid4()),
            "audit_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "session_id": session_id,
            "action": action,
            "payload": payload,
            "created_at": now_utc(),
        }
        await self._audit().insert_one(audit)
        if session_id:
            await self.event_service.append(
                session_id=session_id,
                user_id=principal.user_id,
                event_type=event_type,
                payload=payload,
            )

    def _require(self, principal: ResearchPrincipal, permission: str) -> None:
        if permission not in principal.permissions:
            raise LivePermissionError(f"missing permission: {permission}")

    def _assert_runner_can_start(self, state: dict[str, Any]) -> None:
        if state.get("global_halted") or state.get("broker_halted"):
            raise LiveSafetyError("live runtime is halted")
        if not state.get("oauth_token_present"):
            raise LiveSafetyError("broker OAuth authorization is missing")
        mandate = state.get("mandate")
        if not mandate or mandate.get("expired"):
            raise LiveSafetyError("active mandate is required before runner start")
