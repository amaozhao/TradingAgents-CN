import pytest

from app.core.coreconfig import settings
from app.services import appstockdataservice as stock_data_service
from app.services.appstockdataservice import StockDataService


@pytest.mark.asyncio
async def test_get_stock_basic_info_uses_postgres_when_enabled(monkeypatch):
    service = StockDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(symbol, source):
        assert symbol == "1"
        assert source == "tushare"
        return {
            "code": "000001",
            "symbol": "000001",
            "name": "平安银行",
            "source": "tushare",
            "market": "深圳证券交易所",
        }

    monkeypatch.setattr(service, "_get_stock_basic_info_from_postgres", fake_pg)

    result = await service.get_stock_basic_info("1", source="tushare")

    assert result is not None
    assert result.symbol == "000001"
    assert result.name == "平安银行"
    assert result.source == "tushare"


@pytest.mark.asyncio
async def test_get_market_quotes_uses_postgres_when_enabled(monkeypatch):
    service = StockDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(symbol):
        assert symbol == "1"
        return {
            "code": "000001",
            "symbol": "000001",
            "close": 10.2,
            "pct_chg": 1.2,
            "source": "tushare",
        }

    monkeypatch.setattr(service, "_get_market_quotes_from_postgres", fake_pg)

    result = await service.get_market_quotes("1")

    assert result is not None
    assert result.symbol == "000001"
    assert result.close == 10.2
    assert result.pct_chg == 1.2


@pytest.mark.asyncio
async def test_get_stock_list_uses_postgres_when_enabled(monkeypatch):
    service = StockDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(**kwargs):
        assert kwargs["source"] == "akshare"
        return [
            {
                "code": "000001",
                "symbol": "000001",
                "name": "平安银行",
                "source": "akshare",
            }
        ]

    monkeypatch.setattr(service, "_get_stock_list_from_postgres", fake_pg)

    result = await service.get_stock_list(source="akshare")

    assert len(result) == 1
    assert result[0].symbol == "000001"
    assert result[0].source == "akshare"


@pytest.mark.asyncio
async def test_get_market_quotes_falls_back_to_mongo_when_postgres_misses(monkeypatch):
    service = StockDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(_symbol):
        return None

    monkeypatch.setattr(service, "_get_market_quotes_from_postgres", fake_pg)
    monkeypatch.setattr(
        stock_data_service,
        "get_mongo_db",
        lambda: FakeMongoDB(
            {
                "market_quotes": {
                    "code": "000001",
                    "symbol": "000001",
                    "close": 10.2,
                    "pct_chg": 1.2,
                }
            }
        ),
    )

    result = await service.get_market_quotes("1")

    assert result is not None
    assert result.symbol == "000001"
    assert result.close == 10.2


class FakeMongoDB:
    def __init__(self, documents):
        self.documents = documents

    def __getitem__(self, collection):
        return FakeMongoCollection(self.documents[collection])


class FakeMongoCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, *_args, **_kwargs):
        return self.document
