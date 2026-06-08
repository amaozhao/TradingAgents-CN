from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .models import now_utc


class ResearchArtifactService:
    def _artifacts(self):
        return get_postgres_db().research_artifacts

    async def create_artifact(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        artifact = {
            "_id": str(uuid.uuid4()),
            "artifact_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_id": str(user_id),
            "artifact_type": artifact_type,
            "payload": payload,
            "created_at": now_utc(),
            "updated_at": now_utc(),
        }
        await self._artifacts().insert_one(artifact)
        return artifact

    async def get_artifact(
        self, artifact_id: str, user_id: str
    ) -> dict[str, Any] | None:
        return await self._artifacts().find_one(
            {"artifact_id": artifact_id, "user_id": str(user_id)}
        )
