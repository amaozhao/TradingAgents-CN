from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .models import now_utc


class ResearchSessionService:
    def _sessions(self):
        return get_postgres_db().research_sessions

    def _messages(self):
        return get_postgres_db().research_messages

    async def create_session(
        self, principal: ResearchPrincipal, title: str | None = None
    ) -> dict[str, Any]:
        now = now_utc()
        session = {
            "_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "title": title or "新研究会话",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        await self._sessions().insert_one(session)
        return session

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        cursor = self._sessions().find({"user_id": str(user_id)}).sort(
            "updated_at", -1
        )
        return [document async for document in cursor]

    async def get_session(
        self, session_id: str, user_id: str
    ) -> dict[str, Any] | None:
        return await self._sessions().find_one(
            {"session_id": session_id, "user_id": str(user_id)}
        )

    async def append_message(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        session = await self.get_session(session_id, user_id)
        if not session:
            return None

        now = now_utc()
        message = {
            "_id": str(uuid.uuid4()),
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": str(user_id),
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": now,
        }
        await self._messages().insert_one(message)
        return message

    async def list_messages(self, session_id: str, user_id: str) -> list[dict[str, Any]]:
        session = await self.get_session(session_id, user_id)
        if not session:
            return []
        cursor = self._messages().find(
            {"session_id": session_id, "user_id": str(user_id)}
        ).sort("created_at", 1)
        return [document async for document in cursor]
