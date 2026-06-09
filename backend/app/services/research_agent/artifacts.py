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

    async def list_artifacts(
        self,
        *,
        session_id: str,
        user_id: str,
        artifact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"session_id": session_id, "user_id": str(user_id)}
        if artifact_type:
            query["artifact_type"] = artifact_type
        cursor = self._artifacts().find(query).sort("created_at", -1)
        return [document async for document in cursor]

    async def list_user_artifacts(
        self,
        *,
        user_id: str,
        artifact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": str(user_id)}
        if artifact_type:
            query["artifact_type"] = artifact_type
        cursor = self._artifacts().find(query).sort("created_at", -1)
        return [document async for document in cursor]

    async def find_artifact_by_payload_value(
        self,
        *,
        user_id: str,
        artifact_type: str,
        payload_key: str,
        payload_value: str,
    ) -> dict[str, Any] | None:
        for artifact in await self.list_user_artifacts(
            user_id=user_id, artifact_type=artifact_type
        ):
            payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else {}
            if artifact.get("artifact_id") == payload_value or payload.get(payload_key) == payload_value:
                return artifact
        return None
