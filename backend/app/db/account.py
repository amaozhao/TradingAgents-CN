from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select

from app.models.table import UserAccount


def build_user_by_username_select(username: str) -> Select:
    return select(UserAccount).where(
        UserAccount.deleted.is_(False),
        UserAccount.username == username,
    )


def build_user_by_legacy_id_select(legacy_id: str) -> Select:
    return select(UserAccount).where(
        UserAccount.deleted.is_(False),
        UserAccount.legacy_id == legacy_id,
    )


def build_user_list_select(*, skip: int, limit: int) -> Select:
    return (
        select(UserAccount)
        .where(UserAccount.deleted.is_(False))
        .order_by(UserAccount.created_at.desc())
        .offset(skip)
        .limit(limit)
    )


async def get_user_by_username(session, username: str) -> dict[str, Any] | None:
    result = await session.execute(build_user_by_username_select(username))
    row = result.scalars().first()
    return _user_account_to_dict(row) if row else None


async def get_user_by_legacy_id(session, legacy_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_user_by_legacy_id_select(legacy_id))
    row = result.scalars().first()
    return _user_account_to_dict(row) if row else None


async def list_users(session, *, skip: int, limit: int) -> list[dict[str, Any]]:
    result = await session.execute(build_user_list_select(skip=skip, limit=limit))
    return [_user_account_to_dict(row) for row in result.scalars()]


def _user_account_to_dict(row: UserAccount) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "_id": str(payload.get("_id") or row.legacy_id),
        "legacy_id": row.legacy_id,
        "username": row.username,
        "email": row.email,
        "is_active": row.is_active,
        "is_admin": row.is_admin,
        "created_at": payload.get("created_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at")
        or (row.updated_at.isoformat() if row.updated_at else None),
    }
    return {key: value for key, value in data.items() if value is not None}
