import pytest

from app.core.config import settings
from app.services.message import InternalMessageQueryParams, InternalMessageService, InternalMessageStats
from app.services.social import SocialMediaQueryParams, SocialMediaService, SocialMediaStats


@pytest.mark.asyncio
async def test_internal_messages_query_uses_postgres_when_enabled(monkeypatch):
    service = InternalMessageService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(params):
        assert params.symbol == "000001"
        return [
            {
                "message_id": "msg-1",
                "symbol": "000001",
                "message_type": "research_report",
                "created_time": "2026-06-03T10:00:00",
            }
        ]

    monkeypatch.setattr(service, "_query_internal_messages_from_postgres", fake_pg)

    result = await service.query_internal_messages(InternalMessageQueryParams(symbol="000001"))

    assert result == [
        {
            "message_id": "msg-1",
            "symbol": "000001",
            "message_type": "research_report",
            "created_time": "2026-06-03T10:00:00",
        }
    ]


@pytest.mark.asyncio
async def test_social_media_query_uses_postgres_when_enabled(monkeypatch):
    service = SocialMediaService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(params):
        assert params.symbol == "000001"
        return [
            {
                "message_id": "social-1",
                "platform": "weibo",
                "symbol": "000001",
                "publish_time": "2026-06-03T10:00:00",
            }
        ]

    monkeypatch.setattr(service, "_query_social_media_messages_from_postgres", fake_pg)

    result = await service.query_social_media_messages(SocialMediaQueryParams(symbol="000001"))

    assert result == [
        {
            "message_id": "social-1",
            "platform": "weibo",
            "symbol": "000001",
            "publish_time": "2026-06-03T10:00:00",
        }
    ]


@pytest.mark.asyncio
async def test_internal_search_and_stats_use_postgres_when_enabled(monkeypatch):
    service = InternalMessageService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_search(query, *, symbol=None, access_level=None, limit=50):
        assert query == "alpha"
        assert symbol == "000001"
        assert access_level == "internal"
        assert limit == 10
        return [{"message_id": "msg-1"}]

    async def fake_stats(**kwargs):
        assert kwargs["symbol"] == "000001"
        return InternalMessageStats(total_count=2, message_types={"research_report": 2})

    monkeypatch.setattr(service, "_search_messages_from_postgres", fake_search)
    monkeypatch.setattr(service, "_get_internal_statistics_from_postgres", fake_stats)

    messages = await service.search_messages("alpha", symbol="000001", access_level="internal", limit=10)
    stats = await service.get_internal_statistics(symbol="000001")

    assert messages == [{"message_id": "msg-1"}]
    assert stats.total_count == 2
    assert stats.message_types == {"research_report": 2}


@pytest.mark.asyncio
async def test_social_search_and_stats_use_postgres_when_enabled(monkeypatch):
    service = SocialMediaService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_search(query, *, symbol=None, platform=None, limit=50):
        assert query == "alpha"
        assert symbol == "000001"
        assert platform == "weibo"
        assert limit == 10
        return [{"message_id": "social-1"}]

    async def fake_stats(**kwargs):
        assert kwargs["symbol"] == "000001"
        return SocialMediaStats(total_count=2, positive_count=1)

    monkeypatch.setattr(service, "_search_messages_from_postgres", fake_search)
    monkeypatch.setattr(service, "_get_social_media_statistics_from_postgres", fake_stats)

    messages = await service.search_messages("alpha", symbol="000001", platform="weibo", limit=10)
    stats = await service.get_social_media_statistics(symbol="000001")

    assert messages == [{"message_id": "social-1"}]
    assert stats.total_count == 2
    assert stats.positive_count == 1
