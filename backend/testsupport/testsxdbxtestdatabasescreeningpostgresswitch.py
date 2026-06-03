import pytest

from app.core.coreconfig import settings
from app.services.databasescreeningservice import DatabaseScreeningService


@pytest.mark.asyncio
async def test_database_screening_uses_postgres_when_enabled(monkeypatch):
    service = DatabaseScreeningService()

    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_screen_with_postgres(**_kwargs):
        return [
            {
                "code": "000001",
                "name": "平安银行",
                "industry": "银行",
                "source": "akshare",
                "total_mv": 100,
                "close": 10.2,
            }
        ], 1

    monkeypatch.setattr(service, "_screen_with_postgres", fake_screen_with_postgres)

    results, total = await service.screen_stocks(
        conditions=[{"field": "industry", "operator": "contains", "value": "银行"}],
        source="akshare",
    )

    assert total == 1
    assert results[0]["code"] == "000001"
    assert results[0]["close"] == 10.2
    assert results[0]["source"] == "akshare"
