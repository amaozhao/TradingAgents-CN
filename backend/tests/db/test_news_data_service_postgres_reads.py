import pytest

from app.core.config import settings
from app.services.news_data_service import NewsDataService, NewsQueryParams


@pytest.mark.asyncio
async def test_query_news_uses_postgres_when_enabled(monkeypatch):
    service = NewsDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(params):
        assert params.symbol == "000001"
        return [
            {
                "symbol": "000001",
                "title": "平安银行新闻",
                "publish_time": "2026-06-03T10:00:00",
                "data_source": "akshare",
            }
        ]

    monkeypatch.setattr(service, "_query_news_from_postgres", fake_pg)

    result = await service.query_news(NewsQueryParams(symbol="000001"))

    assert result == [
        {
            "symbol": "000001",
            "title": "平安银行新闻",
            "publish_time": "2026-06-03T10:00:00",
            "data_source": "akshare",
        }
    ]
