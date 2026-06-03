from __future__ import annotations

from typing import Any

from sqlalchemy import Select, asc, case, cast, desc, func, Integer, or_, select

from app.db.model import InternalMessageDocument, SocialMediaMessageDocument


INTERNAL_SORT_COLUMNS = {
    "created_time": InternalMessageDocument.created_time,
    "importance": InternalMessageDocument.importance,
    "confidence_level": InternalMessageDocument.confidence_level,
    "updated_at": InternalMessageDocument.updated_at,
}

SOCIAL_SORT_COLUMNS = {
    "publish_time": SocialMediaMessageDocument.publish_time,
    "importance": SocialMediaMessageDocument.importance,
    "influence_score": SocialMediaMessageDocument.influence_score,
    "engagement_rate": SocialMediaMessageDocument.engagement_rate,
    "updated_at": SocialMediaMessageDocument.updated_at,
}


def build_internal_messages_select(params) -> Select:
    statement = select(InternalMessageDocument).where(*_internal_filters(params))
    sort_column = INTERNAL_SORT_COLUMNS.get(params.sort_by, InternalMessageDocument.created_time)
    statement = statement.order_by(desc(sort_column) if params.sort_order == -1 else asc(sort_column))
    return statement.offset(params.skip).limit(params.limit)


def build_social_media_messages_select(params) -> Select:
    statement = select(SocialMediaMessageDocument).where(*_social_filters(params))
    sort_column = SOCIAL_SORT_COLUMNS.get(params.sort_by, SocialMediaMessageDocument.publish_time)
    statement = statement.order_by(desc(sort_column) if params.sort_order == -1 else asc(sort_column))
    return statement.offset(params.skip).limit(params.limit)


def build_internal_messages_search_select(
    query: str,
    *,
    symbol: str | None,
    access_level: str | None,
    limit: int,
) -> Select:
    keyword = f"%{query}%"
    filters = [
        InternalMessageDocument.deleted.is_(False),
        or_(
            InternalMessageDocument.payload["title"].astext.ilike(keyword),
            InternalMessageDocument.payload["content"].astext.ilike(keyword),
            InternalMessageDocument.payload["summary"].astext.ilike(keyword),
            InternalMessageDocument.payload["keywords"].astext.ilike(keyword),
        ),
    ]
    if symbol:
        filters.append(InternalMessageDocument.symbol == symbol)
    if access_level:
        filters.append(InternalMessageDocument.access_level == access_level)
    return (
        select(InternalMessageDocument)
        .where(*filters)
        .order_by(desc(InternalMessageDocument.created_time))
        .limit(limit)
    )


def build_social_media_messages_search_select(
    query: str,
    *,
    symbol: str | None,
    platform: str | None,
    limit: int,
) -> Select:
    keyword = f"%{query}%"
    filters = [
        SocialMediaMessageDocument.deleted.is_(False),
        or_(
            SocialMediaMessageDocument.payload["content"].astext.ilike(keyword),
            SocialMediaMessageDocument.payload["text"].astext.ilike(keyword),
            SocialMediaMessageDocument.payload["title"].astext.ilike(keyword),
            SocialMediaMessageDocument.payload["hashtags"].astext.ilike(keyword),
            SocialMediaMessageDocument.payload["keywords"].astext.ilike(keyword),
        ),
    ]
    if symbol:
        filters.append(SocialMediaMessageDocument.symbol == symbol)
    if platform:
        filters.append(SocialMediaMessageDocument.platform == platform)
    return (
        select(SocialMediaMessageDocument)
        .where(*filters)
        .order_by(desc(SocialMediaMessageDocument.publish_time))
        .limit(limit)
    )


def build_internal_message_stats_totals_select(
    *, symbol=None, start_time=None, end_time=None
) -> Select:
    return select(
        func.count().label("total_count"),
        func.coalesce(func.avg(InternalMessageDocument.confidence_level), 0).label("avg_confidence"),
    ).where(*_internal_stats_filters(symbol=symbol, start_time=start_time, end_time=end_time))


def build_social_media_stats_totals_select(
    *, symbol=None, start_time=None, end_time=None
) -> Select:
    filters = _social_stats_filters(symbol=symbol, start_time=start_time, end_time=end_time)
    engagement = SocialMediaMessageDocument.payload["engagement"]
    return select(
        func.count().label("total_count"),
        func.coalesce(func.sum(case((SocialMediaMessageDocument.sentiment == "positive", 1), else_=0)), 0).label("positive_count"),
        func.coalesce(func.sum(case((SocialMediaMessageDocument.sentiment == "negative", 1), else_=0)), 0).label("negative_count"),
        func.coalesce(func.sum(case((SocialMediaMessageDocument.sentiment == "neutral", 1), else_=0)), 0).label("neutral_count"),
        func.coalesce(func.sum(cast(engagement["views"].astext, Integer)), 0).label("total_views"),
        func.coalesce(func.sum(cast(engagement["likes"].astext, Integer)), 0).label("total_likes"),
        func.coalesce(func.sum(cast(engagement["shares"].astext, Integer)), 0).label("total_shares"),
        func.coalesce(func.sum(cast(engagement["comments"].astext, Integer)), 0).label("total_comments"),
        func.coalesce(func.avg(SocialMediaMessageDocument.engagement_rate), 0).label("avg_engagement_rate"),
    ).where(*filters)


async def query_internal_messages(session, params) -> list[dict[str, Any]]:
    result = await session.execute(build_internal_messages_select(params))
    return [_internal_to_dict(row) for row in result.scalars()]


async def query_social_media_messages(session, params) -> list[dict[str, Any]]:
    result = await session.execute(build_social_media_messages_select(params))
    return [_social_to_dict(row) for row in result.scalars()]


async def search_internal_messages(
    session,
    query: str,
    *,
    symbol: str | None = None,
    access_level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_internal_messages_search_select(
            query,
            symbol=symbol,
            access_level=access_level,
            limit=limit,
        )
    )
    return [_internal_to_dict(row) for row in result.scalars()]


async def search_social_media_messages(
    session,
    query: str,
    *,
    symbol: str | None = None,
    platform: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_social_media_messages_search_select(
            query,
            symbol=symbol,
            platform=platform,
            limit=limit,
        )
    )
    return [_social_to_dict(row) for row in result.scalars()]


async def get_internal_message_stats(session, *, symbol=None, start_time=None, end_time=None) -> dict[str, Any]:
    totals_result = await session.execute(
        build_internal_message_stats_totals_select(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
        )
    )
    totals = totals_result.one()
    filters = _internal_stats_filters(symbol=symbol, start_time=start_time, end_time=end_time)
    return {
        "total_count": int(totals.total_count or 0),
        "avg_confidence": float(totals.avg_confidence or 0),
        "message_types": await _count_by(session, InternalMessageDocument.message_type, filters),
        "categories": await _count_by(session, InternalMessageDocument.category, filters),
        "departments": await _count_by(session, InternalMessageDocument.department, filters),
        "importance_levels": await _count_by(session, InternalMessageDocument.importance, filters),
        "ratings": await _count_by(session, InternalMessageDocument.rating, filters),
    }


async def get_social_media_stats(session, *, symbol=None, start_time=None, end_time=None) -> dict[str, Any]:
    result = await session.execute(
        build_social_media_stats_totals_select(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
        )
    )
    totals = result.one()
    return {
        "total_count": int(totals.total_count or 0),
        "positive_count": int(totals.positive_count or 0),
        "negative_count": int(totals.negative_count or 0),
        "neutral_count": int(totals.neutral_count or 0),
        "total_views": int(totals.total_views or 0),
        "total_likes": int(totals.total_likes or 0),
        "total_shares": int(totals.total_shares or 0),
        "total_comments": int(totals.total_comments or 0),
        "avg_engagement_rate": float(totals.avg_engagement_rate or 0),
    }


def _internal_filters(params) -> list[Any]:
    filters = [InternalMessageDocument.deleted.is_(False)]
    if params.symbol:
        filters.append(InternalMessageDocument.symbol == params.symbol)
    elif params.symbols:
        filters.append(InternalMessageDocument.symbol.in_(params.symbols))
    if params.message_type:
        filters.append(InternalMessageDocument.message_type == params.message_type)
    if params.category:
        filters.append(InternalMessageDocument.category == params.category)
    if params.source_type:
        filters.append(InternalMessageDocument.source_type == params.source_type)
    if params.department:
        filters.append(InternalMessageDocument.department == params.department)
    if params.author:
        filters.append(InternalMessageDocument.payload["source"]["author"].astext == params.author)
    if params.start_time:
        filters.append(InternalMessageDocument.created_time >= params.start_time)
    if params.end_time:
        filters.append(InternalMessageDocument.created_time <= params.end_time)
    if params.importance:
        filters.append(InternalMessageDocument.importance == params.importance)
    if params.access_level:
        filters.append(InternalMessageDocument.access_level == params.access_level)
    if params.min_confidence:
        filters.append(InternalMessageDocument.confidence_level >= params.min_confidence)
    if params.rating:
        filters.append(InternalMessageDocument.rating == params.rating)
    if params.keywords:
        filters.append(_jsonb_array_contains_any(InternalMessageDocument.payload["keywords"], params.keywords))
    if params.tags:
        filters.append(_jsonb_array_contains_any(InternalMessageDocument.payload["tags"], params.tags))
    return filters


def _social_filters(params) -> list[Any]:
    filters = [SocialMediaMessageDocument.deleted.is_(False)]
    if params.symbol:
        filters.append(SocialMediaMessageDocument.symbol == params.symbol)
    elif params.symbols:
        filters.append(SocialMediaMessageDocument.symbol.in_(params.symbols))
    if params.platform:
        filters.append(SocialMediaMessageDocument.platform == params.platform)
    if params.message_type:
        filters.append(SocialMediaMessageDocument.message_type == params.message_type)
    if params.start_time:
        filters.append(SocialMediaMessageDocument.publish_time >= params.start_time)
    if params.end_time:
        filters.append(SocialMediaMessageDocument.publish_time <= params.end_time)
    if params.sentiment:
        filters.append(SocialMediaMessageDocument.sentiment == params.sentiment)
    if params.importance:
        filters.append(SocialMediaMessageDocument.importance == params.importance)
    if params.min_influence_score:
        filters.append(SocialMediaMessageDocument.influence_score >= params.min_influence_score)
    if params.min_engagement_rate:
        filters.append(SocialMediaMessageDocument.engagement_rate >= params.min_engagement_rate)
    if params.verified_only:
        filters.append(SocialMediaMessageDocument.verified.is_(True))
    if params.keywords:
        filters.append(_jsonb_array_contains_any(SocialMediaMessageDocument.payload["keywords"], params.keywords))
    if params.hashtags:
        filters.append(_jsonb_array_contains_any(SocialMediaMessageDocument.payload["hashtags"], params.hashtags))
    return filters


def _internal_stats_filters(*, symbol=None, start_time=None, end_time=None) -> list[Any]:
    filters = [InternalMessageDocument.deleted.is_(False)]
    if symbol:
        filters.append(InternalMessageDocument.symbol == symbol)
    if start_time:
        filters.append(InternalMessageDocument.created_time >= start_time)
    if end_time:
        filters.append(InternalMessageDocument.created_time <= end_time)
    return filters


def _social_stats_filters(*, symbol=None, start_time=None, end_time=None) -> list[Any]:
    filters = [SocialMediaMessageDocument.deleted.is_(False)]
    if symbol:
        filters.append(SocialMediaMessageDocument.symbol == symbol)
    if start_time:
        filters.append(SocialMediaMessageDocument.publish_time >= start_time)
    if end_time:
        filters.append(SocialMediaMessageDocument.publish_time <= end_time)
    return filters


async def _count_by(session, column, filters: list[Any]) -> dict[str, int]:
    result = await session.execute(
        select(column, func.count().label("count"))
        .where(*filters)
        .group_by(column)
    )
    return {str(key): int(count) for key, count in result if key is not None}


def _jsonb_array_contains_any(path, values: list[str]):
    return or_(*(path.contains([value]) for value in values))


def _internal_to_dict(row: InternalMessageDocument) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "message_id": row.message_id,
        "symbol": row.symbol,
        "message_type": row.message_type,
        "category": row.category,
        "importance": row.importance,
        "access_level": row.access_level,
        "confidence_level": float(row.confidence_level) if row.confidence_level is not None else None,
        "created_time": row.created_time.isoformat() if row.created_time else None,
    }
    return {key: value for key, value in data.items() if value is not None}


def _social_to_dict(row: SocialMediaMessageDocument) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "message_id": row.message_id,
        "platform": row.platform,
        "symbol": row.symbol,
        "message_type": row.message_type,
        "sentiment": row.sentiment,
        "importance": row.importance,
        "publish_time": row.publish_time.isoformat() if row.publish_time else None,
    }
    return {key: value for key, value in data.items() if value is not None}
