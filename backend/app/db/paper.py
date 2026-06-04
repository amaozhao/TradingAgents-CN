from __future__ import annotations

from typing import Any

from sqlalchemy import Select, desc, select

from app.db.model import PaperAccount, PaperOrder, PaperPosition


def build_paper_account_select(user_id: str) -> Select:
    return select(PaperAccount).where(
        PaperAccount.deleted.is_(False),
        PaperAccount.user_id == user_id,
    )


def build_paper_positions_select(user_id: str) -> Select:
    return select(PaperPosition).where(
        PaperPosition.deleted.is_(False),
        PaperPosition.user_id == user_id,
    )


def build_paper_orders_select(user_id: str, *, limit: int) -> Select:
    return (
        select(PaperOrder)
        .where(PaperOrder.deleted.is_(False), PaperOrder.user_id == user_id)
        .order_by(desc(PaperOrder.created_at))
        .limit(limit)
    )


async def get_paper_account(session, user_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_paper_account_select(user_id))
    row = result.scalars().first()
    return _document_to_dict(row) if row else None


async def list_paper_positions(session, user_id: str) -> list[dict[str, Any]]:
    result = await session.execute(build_paper_positions_select(user_id))
    return [_document_to_dict(row) for row in result.scalars()]


async def list_paper_orders(
    session, user_id: str, *, limit: int
) -> list[dict[str, Any]]:
    result = await session.execute(build_paper_orders_select(user_id, limit=limit))
    return [_document_to_dict(row) for row in result.scalars()]


def _document_to_dict(row) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "legacy_id": row.legacy_id,
        "user_id": row.user_id,
        "created_at": payload.get("created_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at")
        or (row.updated_at.isoformat() if row.updated_at else None),
    }
    if hasattr(row, "code"):
        data["code"] = row.code
    if hasattr(row, "market"):
        data["market"] = row.market
    if hasattr(row, "currency"):
        data["currency"] = row.currency
    if hasattr(row, "quantity"):
        data["quantity"] = row.quantity
    if hasattr(row, "side"):
        data["side"] = row.side
    if hasattr(row, "status"):
        data["status"] = row.status
    return {key: value for key, value in data.items() if value is not None}
