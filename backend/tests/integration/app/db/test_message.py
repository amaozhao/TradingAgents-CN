from datetime import datetime

from sqlalchemy.dialects import postgresql

from app.db.message import (
    build_internal_message_stats_totals_select,
    build_internal_messages_search_select,
    build_internal_messages_select,
    build_social_media_messages_search_select,
    build_social_media_messages_select,
    build_social_media_stats_totals_select,
)
from app.services.message import InternalMessageQueryParams
from app.services.social import SocialMediaQueryParams


def test_internal_messages_select_filters_split_columns_for_common_query():
    params = InternalMessageQueryParams(
        symbol="000001",
        message_type="research_report",
        category="fundamental_analysis",
        source_type="internal_research",
        department="research",
        start_time=datetime(2026, 6, 1),
        end_time=datetime(2026, 6, 3),
        importance="high",
        access_level="internal",
        min_confidence=0.8,
        rating="buy",
        limit=20,
        skip=10,
    )

    sql = _compile(build_internal_messages_select(params))

    assert "FROM internal_messages" in sql
    assert "internal_messages.deleted IS false" in sql
    assert "internal_messages.symbol =" in sql
    assert "internal_messages.message_type =" in sql
    assert "internal_messages.category =" in sql
    assert "internal_messages.source_type =" in sql
    assert "internal_messages.department =" in sql
    assert "internal_messages.created_time >=" in sql
    assert "internal_messages.created_time <=" in sql
    assert "internal_messages.importance =" in sql
    assert "internal_messages.access_level =" in sql
    assert "internal_messages.confidence_level >=" in sql
    assert "internal_messages.rating =" in sql
    assert "ORDER BY internal_messages.created_time DESC" in sql


def test_social_media_messages_select_filters_split_columns_for_common_query():
    params = SocialMediaQueryParams(
        symbol="000001",
        platform="weibo",
        message_type="post",
        start_time=datetime(2026, 6, 1),
        end_time=datetime(2026, 6, 3),
        sentiment="positive",
        importance="high",
        min_influence_score=80,
        min_engagement_rate=0.2,
        verified_only=True,
        limit=20,
        skip=10,
    )

    sql = _compile(build_social_media_messages_select(params))

    assert "FROM social_media_messages" in sql
    assert "social_media_messages.deleted IS false" in sql
    assert "social_media_messages.symbol =" in sql
    assert "social_media_messages.platform =" in sql
    assert "social_media_messages.message_type =" in sql
    assert "social_media_messages.publish_time >=" in sql
    assert "social_media_messages.publish_time <=" in sql
    assert "social_media_messages.sentiment =" in sql
    assert "social_media_messages.importance =" in sql
    assert "social_media_messages.influence_score >=" in sql
    assert "social_media_messages.engagement_rate >=" in sql
    assert "social_media_messages.verified IS true" in sql
    assert "ORDER BY social_media_messages.publish_time DESC" in sql


def test_internal_message_stats_uses_split_filter_and_confidence_columns():
    sql = _compile(
        build_internal_message_stats_totals_select(
            symbol="000001",
            start_time=datetime(2026, 6, 1),
            end_time=datetime(2026, 6, 3),
        )
    )

    assert "FROM internal_messages" in sql
    assert "internal_messages.deleted IS false" in sql
    assert "internal_messages.symbol =" in sql
    assert "internal_messages.created_time >=" in sql
    assert "internal_messages.created_time <=" in sql
    assert "avg(internal_messages.confidence_level)" in sql


def test_social_media_stats_uses_split_filter_and_sentiment_columns():
    sql = _compile(
        build_social_media_stats_totals_select(
            symbol="000001",
            start_time=datetime(2026, 6, 1),
            end_time=datetime(2026, 6, 3),
        )
    )

    assert "FROM social_media_messages" in sql
    assert "social_media_messages.deleted IS false" in sql
    assert "social_media_messages.symbol =" in sql
    assert "social_media_messages.publish_time >=" in sql
    assert "social_media_messages.publish_time <=" in sql
    assert "social_media_messages.sentiment =" in sql
    assert "avg(social_media_messages.engagement_rate)" in sql


def test_message_search_is_jsonb_compatibility_path_with_split_scoping():
    internal_sql = _compile(
        build_internal_messages_search_select(
            "alpha",
            symbol="000001",
            access_level="internal",
            limit=20,
        )
    )
    social_sql = _compile(
        build_social_media_messages_search_select(
            "alpha",
            symbol="000001",
            platform="weibo",
            limit=20,
        )
    )

    assert "internal_messages.symbol =" in internal_sql
    assert "internal_messages.access_level =" in internal_sql
    assert "internal_messages.payload" in internal_sql
    assert "ILIKE" in internal_sql

    assert "social_media_messages.symbol =" in social_sql
    assert "social_media_messages.platform =" in social_sql
    assert "social_media_messages.payload" in social_sql
    assert "ILIKE" in social_sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
