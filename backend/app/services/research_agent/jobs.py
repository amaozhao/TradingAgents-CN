from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .events import ResearchEventService
from .models import now_utc


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class ResearchJobService:
    def __init__(self, event_service: ResearchEventService | None = None):
        self.event_service = event_service or ResearchEventService()

    def _jobs(self):
        return get_postgres_db().research_jobs

    async def _emit(
        self, job: dict[str, Any], event_type: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        event_payload = {
            "job_id": job["job_id"],
            "status": job.get("status"),
            **(payload or {}),
        }
        return await self.event_service.append(
            session_id=job["job_id"],
            user_id=job["user_id"],
            event_type=event_type,
            payload=event_payload,
        )

    async def enqueue(
        self,
        *,
        principal: ResearchPrincipal,
        task_type: str,
        resource_id: str,
        payload: dict[str, Any],
        symbol: str | None = None,
    ) -> dict[str, Any]:
        now = now_utc()
        job = {
            "_id": str(uuid.uuid4()),
            "job_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "task_type": task_type,
            "resource_id": resource_id,
            "payload": payload,
            "symbol": symbol,
            "status": "queued",
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        await self._jobs().insert_one(job)
        await self._emit(job, "job_queued")
        return job

    async def get(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._jobs().find_one({"job_id": job_id, "user_id": str(user_id)})

    async def _get_any(self, job_id: str) -> dict[str, Any] | None:
        return await self._jobs().find_one({"job_id": job_id})

    async def cancel(self, job_id: str, user_id: str) -> bool:
        job = await self.get(job_id, user_id)
        if not job or job.get("status") in TERMINAL_STATUSES:
            return False
        updated_at = now_utc()
        await self._jobs().update_one(
            {"job_id": job_id, "user_id": str(user_id)},
            {"$set": {"status": "cancelled", "updated_at": updated_at}},
        )
        job["status"] = "cancelled"
        job["updated_at"] = updated_at
        await self._emit(job, "job_cancelled")
        return True

    async def mark_running(self, job_id: str) -> bool:
        return await self._transition(job_id, "running", "job_running")

    async def mark_completed(self, job_id: str, result: dict[str, Any]) -> bool:
        return await self._transition(
            job_id, "completed", "job_completed", {"result": result}
        )

    async def mark_failed(self, job_id: str, error: str) -> bool:
        return await self._transition(job_id, "failed", "job_failed", {"error": error})

    async def _transition(
        self,
        job_id: str,
        status: str,
        event_type: str,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        job = await self._get_any(job_id)
        if not job:
            return False
        updated_at = now_utc()
        update = {"status": status, "updated_at": updated_at}
        if extra:
            update.update(extra)
        await self._jobs().update_one({"job_id": job_id}, {"$set": update})
        job.update(update)
        await self._emit(job, event_type, extra)
        return True

    async def list_events(
        self, job_id: str, user_id: str, after_event_id: int = 0
    ) -> list[dict[str, Any]]:
        job = await self.get(job_id, user_id)
        if not job:
            return []
        return await self.event_service.list_after(
            session_id=job_id,
            user_id=str(user_id),
            after_event_id=after_event_id,
        )
