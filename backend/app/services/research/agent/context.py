from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .permissions import admin_permissions, normal_user_permissions


@dataclass(frozen=True)
class ResearchPrincipal:
    user_id: str
    role: str
    permissions: frozenset[str]
    session_id: str | None = None

    @classmethod
    def from_user(
        cls, user: dict[str, Any], session_id: str | None = None
    ) -> "ResearchPrincipal":
        user_id = user.get("id") or user.get("user_id")
        if not user_id:
            raise ValueError("user id is required")

        roles = set(user.get("roles") or [])
        is_admin = bool(user.get("is_admin")) or "admin" in roles
        permissions = set(normal_user_permissions())
        if is_admin:
            permissions.update(admin_permissions())

        return cls(
            user_id=str(user_id),
            role="admin" if is_admin else "user",
            permissions=frozenset(permissions),
            session_id=session_id,
        )


@dataclass(frozen=True)
class ToolExecutionContext:
    principal: ResearchPrincipal
    session_id: str | None = None
    request_id: str | None = None
    artifact_writer: Any | None = None
    event_emitter: Any | None = None
    budget: dict[str, Any] | None = None
    timeout: float | None = None
    cancel_token: Any | None = None
