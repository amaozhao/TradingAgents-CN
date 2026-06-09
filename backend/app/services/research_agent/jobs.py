from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .events import ResearchEventService
from .models import now_utc


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class ResearchAttemptService:
    def __init__(self, event_service: ResearchEventService | None = None):
        self.event_service = event_service or ResearchEventService()

    def _attempts(self):
        return get_postgres_db().research_attempts

    async def create(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        now = now_utc()
        attempt = {
            "_id": str(uuid.uuid4()),
            "attempt_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": principal.user_id,
            "job_id": None,
            "status": "queued",
            "prompt": user_message,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "result": None,
        }
        await self._attempts().insert_one(attempt)
        await self._emit(attempt, "attempt.created")
        return attempt

    async def list_for_session(self, session_id: str, user_id: str) -> list[dict[str, Any]]:
        cursor = self._attempts().find(
            {"session_id": session_id, "user_id": str(user_id)}
        ).sort("created_at", 1)
        return [document async for document in cursor]

    async def get(self, attempt_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._attempts().find_one(
            {"attempt_id": attempt_id, "user_id": str(user_id)}
        )

    async def attach_job(self, attempt_id: str, user_id: str, job_id: str) -> bool:
        result = await self._attempts().update_one(
            {"attempt_id": attempt_id, "user_id": str(user_id)},
            {"$set": {"job_id": job_id, "updated_at": now_utc()}},
        )
        return getattr(result, "modified_count", 0) > 0

    async def mark_started(self, attempt_id: str, user_id: str) -> bool:
        return await self._transition(
            attempt_id,
            user_id,
            "running",
            "attempt.started",
            {"started_at": now_utc()},
        )

    async def mark_completed(
        self, attempt_id: str, user_id: str, result: dict[str, Any]
    ) -> bool:
        return await self._transition(
            attempt_id,
            user_id,
            "completed",
            "attempt.completed",
            {"completed_at": now_utc(), "result": result},
        )

    async def mark_failed(self, attempt_id: str, user_id: str, error: str) -> bool:
        return await self._transition(
            attempt_id,
            user_id,
            "failed",
            "attempt.failed",
            {"completed_at": now_utc(), "error": error},
        )

    async def mark_cancelled(self, attempt_id: str, user_id: str) -> bool:
        return await self._transition(
            attempt_id,
            user_id,
            "cancelled",
            "attempt.cancelled",
            {"completed_at": now_utc()},
        )

    async def _transition(
        self,
        attempt_id: str,
        user_id: str,
        status: str,
        event_type: str,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        attempt = await self.get(attempt_id, user_id)
        if not attempt or attempt.get("status") in TERMINAL_STATUSES:
            return False
        now = now_utc()
        update = {"status": status, "updated_at": now, **(extra or {})}
        await self._attempts().update_one(
            {"attempt_id": attempt_id, "user_id": str(user_id)},
            {"$set": update},
        )
        attempt.update(update)
        await self._emit(attempt, event_type)
        return True

    async def _emit(
        self, attempt: dict[str, Any], event_type: str
    ) -> dict[str, Any]:
        return await self.event_service.append(
            session_id=attempt["session_id"],
            user_id=attempt["user_id"],
            event_type=event_type,
            payload={
                "attempt_id": attempt["attempt_id"],
                "job_id": attempt.get("job_id"),
                "status": attempt.get("status"),
                "error": attempt.get("error"),
                "result": attempt.get("result"),
            },
        )


class ResearchJobService:
    def __init__(self, event_service: ResearchEventService | None = None):
        self.event_service = event_service or ResearchEventService()

    def _jobs(self):
        return get_postgres_db().research_jobs

    async def _emit(
        self, job: dict[str, Any], event_type: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        event_session_id = job.get("event_session_id") or job.get("session_id") or job["job_id"]
        event_payload = {
            "job_id": job["job_id"],
            "attempt_id": job.get("attempt_id"),
            "session_id": job.get("session_id"),
            "resource_id": job.get("resource_id"),
            "task_type": job.get("task_type"),
            "status": job.get("status"),
            **(payload or {}),
        }
        return await self.event_service.append(
            session_id=event_session_id,
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
        session_id: str | None = None,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        now = now_utc()
        job = {
            "_id": str(uuid.uuid4()),
            "job_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "session_id": session_id,
            "attempt_id": attempt_id,
            "event_session_id": session_id,
            "task_type": task_type,
            "resource_id": resource_id,
            "payload": payload,
            "symbol": symbol,
            "status": "queued",
            "cancel_requested": False,
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

    async def cancel_active_for_session(
        self, session_id: str, user_id: str
    ) -> list[dict[str, Any]]:
        cursor = self._jobs().find({"session_id": session_id, "user_id": str(user_id)})
        jobs = [document async for document in cursor]
        cancelled: list[dict[str, Any]] = []
        for job in jobs:
            if job.get("status") in TERMINAL_STATUSES:
                continue
            updated_at = now_utc()
            update = {
                "status": "cancelled",
                "cancel_requested": True,
                "updated_at": updated_at,
            }
            await self._jobs().update_one(
                {"job_id": job["job_id"], "user_id": str(user_id)},
                {"$set": update},
            )
            job.update(update)
            await self._emit(job, "job_cancelled")
            cancelled.append(job)
        return cancelled

    async def is_cancelled(self, job_id: str) -> bool:
        job = await self._get_any(job_id)
        return bool(job and (job.get("status") == "cancelled" or job.get("cancel_requested")))

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
        if job.get("status") in TERMINAL_STATUSES:
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
