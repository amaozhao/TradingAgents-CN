from __future__ import annotations

from typing import Any

from sqlalchemy import Select, asc, desc, or_, select

from app.models.table import StockNewsDocument

SORT_COLUMNS = {
    "publish_time": StockNewsDocument.publish_time,
    "updated_at": StockNewsDocument.updated_at,
    "created_at": StockNewsDocument.created_at,
    "importance": StockNewsDocument.importance,
}


def build_news_select(params) -> Select:
    statement = select(StockNewsDocument).where(*_filters(params))
    sort_column = SORT_COLUMNS.get(params.sort_by, StockNewsDocument.publish_time)
    statement = statement.order_by(
        desc(sort_column) if params.sort_order == -1 else asc(sort_column)
    )
    return statement.offset(params.skip).limit(params.limit)


async def query_news(session, params) -> list[dict[str, Any]]:
    result = await session.execute(build_news_select(params))
    return [_news_to_dict(row) for row in result.scalars()]


def _filters(params) -> list[Any]:
    filters: list[Any] = [StockNewsDocument.deleted.is_(False)]
    if params.symbol:
        filters.append(StockNewsDocument.symbol == params.symbol)
    if params.symbols:
        filters.append(StockNewsDocument.symbol.in_(params.symbols))
    if params.start_time:
        filters.append(StockNewsDocument.publish_time >= params.start_time)
    if params.end_time:
        filters.append(StockNewsDocument.publish_time <= params.end_time)
    if params.category:
        filters.append(StockNewsDocument.category == params.category)
    if params.sentiment:
        filters.append(StockNewsDocument.sentiment == params.sentiment)
    if params.importance:
        filters.append(StockNewsDocument.importance == params.importance)
    if params.data_source:
        filters.append(StockNewsDocument.data_source == params.data_source)
    if params.keywords:
        keyword = f"%{' '.join(params.keywords)}%"
        filters.append(
            or_(
                StockNewsDocument.title.ilike(keyword),
                StockNewsDocument.payload["content"].astext.ilike(keyword),
                StockNewsDocument.payload["summary"].astext.ilike(keyword),
            )
        )
    return filters


def _news_to_dict(row: StockNewsDocument) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "symbol": row.symbol,
        "market": row.market,
        "title": row.title,
        "url": row.url,
        "data_source": row.data_source,
        "category": row.category,
        "sentiment": row.sentiment,
        "importance": row.importance,
        "publish_time": row.publish_time.isoformat() if row.publish_time else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return {key: value for key, value in data.items() if value is not None}
