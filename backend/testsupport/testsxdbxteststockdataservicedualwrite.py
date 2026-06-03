from types import SimpleNamespace

import pytest

from app.services import appstockdataservice as stock_data_service
from app.services.appstockdataservice import StockDataService


@pytest.mark.asyncio
async def test_update_stock_basic_info_dual_writes_postgres(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(stock_data_service, "get_mongo_db", lambda: fake_db)

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document.copy()))

    monkeypatch.setattr(stock_data_service, "dual_write_hot_document", fake_dual_write)

    service = StockDataService()
    success = await service.update_stock_basic_info(
        "1",
        {"name": "平安银行"},
        source="tushare",
    )

    assert success is True
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["symbol"] == "000001"
    assert dual_write_calls[0][1]["source"] == "tushare"


@pytest.mark.asyncio
async def test_update_market_quotes_dual_writes_postgres_with_default_source(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(stock_data_service, "get_mongo_db", lambda: fake_db)

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document.copy()))

    monkeypatch.setattr(stock_data_service, "dual_write_hot_document", fake_dual_write)

    service = StockDataService()
    success = await service.update_market_quotes("1", {"close": 10.2})

    assert success is True
    assert dual_write_calls[0][0] == "market_quotes"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["symbol"] == "000001"
    assert dual_write_calls[0][1]["source"] == "tushare"


class FakeDB:
    def __getitem__(self, _collection):
        return FakeUpdateCollection()


class FakeUpdateCollection:
    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(modified_count=1, upserted_id=None)
