from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .models import now_utc


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return json_safe(value.model_dump(mode="json"))
        except TypeError:
            return json_safe(value.model_dump())
    if hasattr(value, "dict"):
        try:
            return json_safe(value.dict())
        except Exception:
            pass
    return str(value)


class ResearchEventService:
    def _events(self):
        return get_postgres_db().research_events

    async def append(
        self,
        *,
        session_id: str,
        user_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = (
            await self._events().count_documents(
                {"session_id": session_id, "user_id": str(user_id)}
            )
        ) + 1
        event = {
            "_id": str(uuid.uuid4()),
            "event_id": event_id,
            "session_id": session_id,
            "user_id": str(user_id),
            "event_type": event_type,
            "payload": json_safe(payload or {}),
            "created_at": now_utc(),
        }
        await self._events().insert_one(event)
        return event

    async def list_after(
        self, *, session_id: str, user_id: str, after_event_id: int = 0
    ) -> list[dict[str, Any]]:
        cursor = self._events().find(
            {
                "session_id": session_id,
                "user_id": str(user_id),
                "event_id": {"$gt": int(after_event_id or 0)},
            }
        ).sort("event_id", 1)
        return [document async for document in cursor]
