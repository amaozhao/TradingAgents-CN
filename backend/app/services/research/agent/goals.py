from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .events import ResearchEventService
from .models import now_utc


GOAL_TERMINAL_STATUSES = {"complete", "completed", "blocked", "cancelled"}


class ResearchGoalConflictError(RuntimeError):
    pass


class ResearchGoalService:
    def __init__(self, event_service: ResearchEventService | None = None) -> None:
        self.event_service = event_service or ResearchEventService()

    def _goals(self):
        return get_postgres_db().research_goals

    async def create_goal(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        title: str,
        description: str = "",
        criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        now = now_utc()
        goal = {
            "_id": str(uuid.uuid4()),
            "goal_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": principal.user_id,
            "title": title.strip() or "研究目标",
            "description": description,
            "criteria": [str(item) for item in (criteria or [])],
            "status": "active",
            "evidence": [],
            "created_at": now,
            "updated_at": now,
        }
        await self._goals().insert_one(goal)
        await self.event_service.append(
            session_id=session_id,
            user_id=principal.user_id,
            event_type="goal.created",
            payload={"goal_id": goal["goal_id"], "status": goal["status"], "title": goal["title"]},
        )
        return goal

    async def get_goal(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._goals().find_one(
            {"session_id": session_id, "user_id": str(user_id)},
            sort=[("updated_at", -1)],
        )

    async def update_goal(
        self,
        *,
        session_id: str,
        user_id: str,
        expected_goal_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        goal = await self.get_goal(session_id, user_id)
        if not goal:
            return None
        if expected_goal_id and goal["goal_id"] != expected_goal_id:
            raise ResearchGoalConflictError("stale goal update rejected")
        allowed = {
            key: value
            for key, value in updates.items()
            if key in {"title", "description", "criteria"} and value is not None
        }
        if "criteria" in allowed:
            allowed["criteria"] = [str(item) for item in (allowed["criteria"] or [])]
        if not allowed:
            return goal
        allowed["updated_at"] = now_utc()
        await self._goals().update_one(
            {"goal_id": goal["goal_id"], "user_id": str(user_id)},
            {"$set": allowed},
        )
        updated = await self.get_goal(session_id, user_id)
        await self.event_service.append(
            session_id=session_id,
            user_id=str(user_id),
            event_type="goal.updated",
            payload={"goal_id": goal["goal_id"], "updates": {k: v for k, v in allowed.items() if k != "updated_at"}},
        )
        return updated

    async def update_status(
        self,
        *,
        session_id: str,
        user_id: str,
        expected_goal_id: str,
        status: str,
        reason: str = "",
    ) -> dict[str, Any] | None:
        goal = await self.get_goal(session_id, user_id)
        if not goal:
            return None
        if expected_goal_id and goal["goal_id"] != expected_goal_id:
            raise ResearchGoalConflictError("stale goal status update rejected")
        clean_status = status.strip().lower() or "active"
        now = now_utc()
        await self._goals().update_one(
            {"goal_id": goal["goal_id"], "user_id": str(user_id)},
            {"$set": {"status": clean_status, "status_reason": reason, "updated_at": now}},
        )
        updated = await self.get_goal(session_id, user_id)
        await self.event_service.append(
            session_id=session_id,
            user_id=str(user_id),
            event_type="goal.updated",
            payload={"goal_id": goal["goal_id"], "status": clean_status, "reason": reason},
        )
        return updated

    async def add_evidence(
        self,
        *,
        session_id: str,
        user_id: str,
        expected_goal_id: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any] | None:
        goal = await self.get_goal(session_id, user_id)
        if not goal:
            return None
        if expected_goal_id and goal["goal_id"] != expected_goal_id:
            raise ResearchGoalConflictError("stale goal evidence update rejected")
        item = {
            "evidence_id": str(uuid.uuid4()),
            "kind": str(evidence.get("kind") or "note"),
            "summary": str(evidence.get("summary") or ""),
            "artifact_id": evidence.get("artifact_id"),
            "message_id": evidence.get("message_id"),
            "metadata": dict(evidence.get("metadata") or {}),
            "created_at": now_utc(),
        }
        existing = list(goal.get("evidence") or [])
        updated_evidence = [*existing, item]
        await self._goals().update_one(
            {"goal_id": goal["goal_id"], "user_id": str(user_id)},
            {"$set": {"evidence": updated_evidence, "updated_at": now_utc()}},
        )
        await self.event_service.append(
            session_id=session_id,
            user_id=str(user_id),
            event_type="goal.evidence",
            payload={"goal_id": goal["goal_id"], "evidence": item},
        )
        return await self.get_goal(session_id, user_id)
