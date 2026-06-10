from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .events import ResearchEventService
from .loop import ModelClientProtocol
from .models import now_utc
from .provider_client import OpenAICompatibleModelClient


TERMINAL_SWARM_STATUSES = {"completed", "failed", "cancelled"}

DEFAULT_SWARM_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "preset": "investment_committee",
        "title": "投资委员会",
        "description": "Research-only multi-role review for investment theses.",
        "workers": ["macro", "fundamental", "risk", "portfolio"],
    },
    {
        "preset": "research_team",
        "title": "研究团队",
        "description": "Evidence collection and critique for market research tasks.",
        "workers": ["researcher", "data", "critic"],
    },
)


class ResearchSwarmService:
    def __init__(self, event_service: ResearchEventService | None = None):
        self.event_service = event_service or ResearchEventService()

    def _runs(self):
        return get_postgres_db().research_swarm_runs

    def _events(self):
        return get_postgres_db().research_swarm_events

    async def list_presets(self) -> list[dict[str, Any]]:
        return [dict(preset) for preset in DEFAULT_SWARM_PRESETS]

    async def create_run(
        self,
        *,
        principal: ResearchPrincipal,
        preset: str,
        variables: dict[str, Any] | None = None,
        session_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        selected = self._preset(preset)
        now = now_utc()
        run = {
            "_id": str(uuid.uuid4()),
            "run_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "session_id": session_id,
            "parent_run_id": parent_run_id,
            "preset": selected["preset"],
            "title": selected["title"],
            "variables": dict(variables or {}),
            "workers": [
                {
                    "worker_id": worker,
                    "status": "queued",
                    "summary": None,
                    "updated_at": now,
                }
                for worker in selected["workers"]
            ],
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "error": None,
        }
        await self._runs().insert_one(run)
        await self._append_run_event(
            run,
            "run_started",
            {
                "preset": run["preset"],
                "variables": run["variables"],
                "workers": run["workers"],
            },
            relay_type="swarm.started",
        )
        for worker in run["workers"]:
            await self._append_run_event(
                run,
                "worker_queued",
                {"worker_id": worker["worker_id"], "status": worker["status"]},
            )
        return run

    async def list_runs(self, user_id: str) -> list[dict[str, Any]]:
        cursor = self._runs().find({"user_id": str(user_id)}).sort("created_at", -1)
        return [document async for document in cursor]

    async def get_run(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._runs().find_one({"run_id": run_id, "user_id": str(user_id)})

    async def list_events(
        self, run_id: str, user_id: str, after_event_id: int = 0
    ) -> list[dict[str, Any]]:
        cursor = self._events().find(
            {
                "run_id": run_id,
                "user_id": str(user_id),
                "event_id": {"$gt": int(after_event_id or 0)},
            }
        ).sort("event_id", 1)
        return [document async for document in cursor]

    async def cancel_run(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        run = await self.get_run(run_id, user_id)
        if not run:
            return None
        if run.get("status") in TERMINAL_SWARM_STATUSES:
            return run
        update = {
            "status": "cancelled",
            "completed_at": now_utc(),
            "updated_at": now_utc(),
        }
        await self._runs().update_one(
            {"run_id": run_id, "user_id": str(user_id)}, {"$set": update}
        )
        run.update(update)
        await self._append_run_event(
            run,
            "run_cancelled",
            {"status": "cancelled"},
            relay_type="swarm.cancelled",
        )
        return run

    async def retry_run(self, run_id: str, principal: ResearchPrincipal) -> dict[str, Any] | None:
        run = await self.get_run(run_id, principal.user_id)
        if not run:
            return None
        return await self.create_run(
            principal=principal,
            preset=str(run.get("preset") or "research_team"),
            variables=dict(run.get("variables") or {}),
            session_id=run.get("session_id"),
            parent_run_id=run_id,
        )

    async def execute_run(
        self,
        *,
        principal: ResearchPrincipal,
        run_id: str,
        model_client_factory: Callable[[ResearchPrincipal], ModelClientProtocol] | None = None,
    ) -> dict[str, Any] | None:
        run = await self.get_run(run_id, principal.user_id)
        if not run:
            return None
        if run.get("status") in TERMINAL_SWARM_STATUSES:
            return run

        model_client = (model_client_factory or OpenAICompatibleModelClient)(principal)
        summaries: list[dict[str, Any]] = []
        try:
            for worker in list(run.get("workers") or []):
                run = await self.get_run(run_id, principal.user_id) or run
                if run.get("status") == "cancelled":
                    return run
                worker_id = str(worker.get("worker_id") or "worker")
                await self._update_worker(run, worker_id, status="running")
                await self._append_run_event(
                    run,
                    "worker_started",
                    {"worker_id": worker_id, "status": "running"},
                )
                summary = await self._execute_worker(model_client, run, worker_id)
                summaries.append({"worker_id": worker_id, "summary": summary})
                run = await self.get_run(run_id, principal.user_id) or run
                await self._update_worker(run, worker_id, status="completed", summary=summary)
                run = await self.get_run(run_id, principal.user_id) or run
                await self._append_run_event(
                    run,
                    "worker_completed",
                    {"worker_id": worker_id, "status": "completed", "summary": summary},
                )
            update = {
                "status": "completed",
                "summaries": summaries,
                "completed_at": now_utc(),
                "updated_at": now_utc(),
            }
            await self._runs().update_one(
                {"run_id": run_id, "user_id": principal.user_id}, {"$set": update}
            )
            run = await self.get_run(run_id, principal.user_id) or {**run, **update}
            await self._append_run_event(
                run,
                "run_completed",
                {"status": "completed", "summaries": summaries},
                relay_type="swarm.completed",
            )
            return run
        except Exception as exc:
            update = {
                "status": "failed",
                "error": str(exc),
                "completed_at": now_utc(),
                "updated_at": now_utc(),
            }
            await self._runs().update_one(
                {"run_id": run_id, "user_id": principal.user_id}, {"$set": update}
            )
            run = await self.get_run(run_id, principal.user_id) or {**run, **update}
            await self._append_run_event(
                run,
                "run_failed",
                {"status": "failed", "error": str(exc)},
                relay_type="swarm.failed",
            )
            raise

    async def _execute_worker(
        self,
        model_client: ModelClientProtocol,
        run: dict[str, Any],
        worker_id: str,
    ) -> str:
        prompt = (
            "You are a research-only swarm worker inside the current project.\n"
            f"Worker role: {worker_id}.\n"
            f"Preset: {run['preset']}.\n"
            "Use only the variables below. Do not claim live trades were placed.\n"
            f"Variables: {run.get('variables') or {}}\n"
            "Return a concise evidence-oriented finding, risks, and next action."
        )
        parts: list[str] = []
        async for chunk in model_client.stream(
            messages=[
                {
                    "role": "system",
                    "content": "You are a current-project research swarm worker.",
                },
                {"role": "user", "content": prompt},
            ],
            tools=[],
        ):
            if chunk.delta:
                parts.append(chunk.delta)
                await self._append_run_event(
                    run,
                    "worker_delta",
                    {"worker_id": worker_id, "content": chunk.delta},
                )
        summary = "".join(parts).strip()
        return summary or "Worker completed without provider text."

    async def _update_worker(
        self,
        run: dict[str, Any],
        worker_id: str,
        *,
        status: str,
        summary: str | None = None,
    ) -> None:
        workers = []
        for worker in run.get("workers") or []:
            next_worker = dict(worker)
            if str(next_worker.get("worker_id")) == worker_id:
                next_worker["status"] = status
                next_worker["updated_at"] = now_utc()
                if summary is not None:
                    next_worker["summary"] = summary
            workers.append(next_worker)
        await self._runs().update_one(
            {"run_id": run["run_id"], "user_id": str(run["user_id"])},
            {"$set": {"workers": workers, "updated_at": now_utc()}},
        )

    async def _append_run_event(
        self,
        run: dict[str, Any],
        event_type: str,
        payload: dict[str, Any],
        relay_type: str = "swarm.event",
    ) -> dict[str, Any]:
        event_id = (
            await self._events().count_documents(
                {"run_id": run["run_id"], "user_id": str(run["user_id"])}
            )
        ) + 1
        event = {
            "_id": str(uuid.uuid4()),
            "event_id": event_id,
            "run_id": run["run_id"],
            "session_id": run.get("session_id"),
            "user_id": str(run["user_id"]),
            "event_type": event_type,
            "payload": {
                "run_id": run["run_id"],
                "preset": run["preset"],
                "status": run["status"],
                **payload,
            },
            "created_at": now_utc(),
        }
        await self._events().insert_one(event)
        if run.get("session_id"):
            relay_payload = {
                "run_id": run["run_id"],
                "preset": run["preset"],
                "status": run["status"],
                "event": {"type": event_type, **payload},
            }
            await self.event_service.append(
                session_id=str(run["session_id"]),
                user_id=str(run["user_id"]),
                event_type=relay_type,
                payload=relay_payload,
            )
        return event

    def _preset(self, preset: str) -> dict[str, Any]:
        for item in DEFAULT_SWARM_PRESETS:
            if item["preset"] == preset:
                return dict(item)
        allowed = ", ".join(item["preset"] for item in DEFAULT_SWARM_PRESETS)
        raise ValueError(f"unknown swarm preset: {preset}; allowed: {allowed}")
