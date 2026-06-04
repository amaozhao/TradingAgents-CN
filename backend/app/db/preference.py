from __future__ import annotations

from typing import Any

from sqlalchemy import Select, desc, select

from app.models.table import UserFavorite, UserTag


def build_user_favorites_select(user_id: str) -> Select:
    return (
        select(UserFavorite)
        .where(UserFavorite.user_id == str(user_id), UserFavorite.deleted.is_(False))
        .order_by(desc(UserFavorite.created_at))
    )


def build_user_tags_select(user_id: str) -> Select:
    return (
        select(UserTag)
        .where(UserTag.user_id == str(user_id), UserTag.deleted.is_(False))
        .order_by(UserTag.sort_order.asc(), UserTag.name.asc())
    )


async def list_user_favorites(session, user_id: str) -> list[dict[str, Any]]:
    result = await session.execute(build_user_favorites_select(user_id))
    return [_favorite_to_dict(row) for row in result.scalars()]


async def list_user_tags(session, user_id: str) -> list[dict[str, Any]]:
    result = await session.execute(build_user_tags_select(user_id))
    return [_tag_to_dict(row) for row in result.scalars()]


def _favorite_to_dict(row: UserFavorite) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "legacy_id": row.legacy_id,
        "user_id": row.user_id,
        "stock_code": row.stock_code,
        "stock_name": row.stock_name,
        "market": row.market,
        "added_at": payload.get("added_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    data.pop("_id", None)
    return {key: value for key, value in data.items() if value is not None}


def _tag_to_dict(row: UserTag) -> dict[str, Any]:
    payload = row.payload or {}
    return {
        "id": str(row.tag_id or payload.get("_id") or row.legacy_id),
        "name": row.name,
        "color": row.color or "#409EFF",
        "sort_order": row.sort_order or 0,
        "created_at": payload.get("created_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at")
        or (row.updated_at.isoformat() if row.updated_at else None),
    }
