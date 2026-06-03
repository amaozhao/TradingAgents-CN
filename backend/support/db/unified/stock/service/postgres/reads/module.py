import pytest

from app.core.config import settings
from app.services.stocks.unified import UnifiedStockService


@pytest.mark.asyncio
async def test_get_daily_quotes_uses_postgres_when_enabled(monkeypatch):
    service = UnifiedStockService(FakeMongoDB({}))
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(**kwargs):
        assert kwargs == {
            "market": "HK",
            "code": "00700",
            "start_date": "2026-01-01",
            "end_date": "2026-06-03",
            "limit": 50,
        }
        return [
            {
                "code": "00700",
                "symbol": "00700",
                "market": "HK",
                "trade_date": "2026-06-03",
                "close": 380.5,
            }
        ]

    monkeypatch.setattr(service, "_get_daily_quotes_from_postgres", fake_pg)

    result = await service.get_daily_quotes(
        market="HK",
        code="00700",
        start_date="2026-01-01",
        end_date="2026-06-03",
        limit=50,
    )

    assert result == [
        {
            "code": "00700",
            "symbol": "00700",
            "market": "HK",
            "trade_date": "2026-06-03",
            "close": 380.5,
        }
    ]


@pytest.mark.asyncio
async def test_get_daily_quotes_falls_back_to_market_mongo_collection(monkeypatch):
    collection = FakeCollection(
        [
            {
                "code": "00700",
                "trade_date": "2026-06-03",
                "close": 380.5,
            }
        ]
    )
    service = UnifiedStockService(FakeMongoDB({"stock_daily_quotes_hk": collection}))
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(**_kwargs):
        return []

    monkeypatch.setattr(service, "_get_daily_quotes_from_postgres", fake_pg)

    result = await service.get_daily_quotes("HK", "00700", limit=20)

    assert collection.find_query == {"code": "00700"}
    assert result[0]["trade_date"] == "2026-06-03"


class FakeMongoDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, collection):
        return self.collections[collection]


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents
        self.find_query = None

    def find(self, query, *_args, **_kwargs):
        self.find_query = query
        return FakeCursor(self.documents)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self.documents[:length]
