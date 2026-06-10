from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_postgres_db

from .context import ResearchPrincipal
from .models import now_utc


class ResearchMemoryService:
    def _memory(self):
        return get_postgres_db().research_agent_memory

    async def remember(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str | None,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = now_utc()
        item = {
            "_id": str(uuid.uuid4()),
            "memory_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "session_id": session_id,
            "content": content,
            "metadata": dict(metadata or {}),
            "created_at": now,
            "updated_at": now,
        }
        await self._memory().insert_one(item)
        return item


class ResearchHypothesisService:
    def _hypotheses(self):
        return get_postgres_db().research_hypotheses

    async def create(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str | None,
        title: str,
        thesis: str,
        evidence: list[dict[str, Any]] | None = None,
        status: str = "open",
    ) -> dict[str, Any]:
        now = now_utc()
        item = {
            "_id": str(uuid.uuid4()),
            "hypothesis_id": str(uuid.uuid4()),
            "user_id": principal.user_id,
            "session_id": session_id,
            "title": title,
            "thesis": thesis,
            "status": status,
            "evidence": list(evidence or []),
            "linked_backtests": [],
            "created_at": now,
            "updated_at": now,
        }
        await self._hypotheses().insert_one(item)
        return item

    async def get(self, hypothesis_id: str, user_id: str) -> dict[str, Any] | None:
        return await self._hypotheses().find_one(
            {"hypothesis_id": hypothesis_id, "user_id": str(user_id)}
        )

    async def update(
        self,
        *,
        hypothesis_id: str,
        user_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        existing = await self.get(hypothesis_id, user_id)
        if not existing:
            return None
        allowed = {key: value for key, value in updates.items() if key in {"title", "thesis", "status", "evidence"}}
        allowed["updated_at"] = now_utc()
        await self._hypotheses().update_one(
            {"hypothesis_id": hypothesis_id, "user_id": str(user_id)},
            {"$set": allowed},
        )
        existing.update(allowed)
        return existing

    async def search(self, *, user_id: str, query: str) -> list[dict[str, Any]]:
        lowered = query.lower()
        cursor = self._hypotheses().find({"user_id": str(user_id)}).sort("created_at", -1)
        matches = []
        async for item in cursor:
            haystack = f"{item.get('title') or ''}\n{item.get('thesis') or ''}".lower()
            if lowered in haystack:
                matches.append(item)
        return matches[:20]

    async def link_backtest(
        self,
        *,
        hypothesis_id: str,
        user_id: str,
        backtest_id: str,
        summary: str = "",
    ) -> dict[str, Any] | None:
        existing = await self.get(hypothesis_id, user_id)
        if not existing:
            return None
        links = list(existing.get("linked_backtests") or [])
        link = {"backtest_id": backtest_id, "summary": summary, "linked_at": now_utc()}
        links.append(link)
        await self._hypotheses().update_one(
            {"hypothesis_id": hypothesis_id, "user_id": str(user_id)},
            {"$set": {"linked_backtests": links, "updated_at": now_utc()}},
        )
        existing["linked_backtests"] = links
        return existing
