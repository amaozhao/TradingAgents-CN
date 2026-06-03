from types import SimpleNamespace

import pytest

from app.routers import stocksync


@pytest.mark.asyncio
async def test_sync_latest_to_market_quotes_dual_writes_postgres(monkeypatch):
    fake_db = SimpleNamespace(
        stock_daily_quotes=FakeDailyQuotesCollection(
            {
                "symbol": "000001",
                "data_source": "tushare",
                "trade_date": "2026-06-03",
                "close": 10.2,
                "pct_chg": 2.0,
                "amount": 1000000.0,
                "volume": 100000,
            }
        ),
        market_quotes=FakeMarketQuotesCollection(),
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="success", reason=None)

    monkeypatch.setattr(stock_sync, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(stock_sync, "dual_write_hot_document", fake_dual_write)

    await stock_sync._sync_latest_to_market_quotes("1")

    assert fake_db.market_quotes.updates[0][0] == {"code": "000001"}
    assert dual_write_calls[0][0] == "market_quotes"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["source"] == "tushare"
    assert dual_write_calls[0][1]["close"] == 10.2


@pytest.mark.asyncio
async def test_stock_sync_basic_info_helper_dual_writes_postgres(monkeypatch):
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="success", reason=None)

    monkeypatch.setattr(stock_sync, "dual_write_hot_document", fake_dual_write)

    await stock_sync._dual_write_stock_basic_info(
        {"code": "000001", "symbol": "000001", "source": "tushare", "name": "平安银行"}
    )

    assert dual_write_calls == [
        (
            "stock_basic_info",
            {"code": "000001", "symbol": "000001", "source": "tushare", "name": "平安银行"},
        )
    ]


class FakeDailyQuotesCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, _query, sort=None):
        return self.document


class FakeMarketQuotesCollection:
    def __init__(self):
        self.updates = []

    async def find_one(self, _query):
        return None

    async def update_one(self, *args, **kwargs):
        self.updates.append((args[0], args[1], kwargs))
        return SimpleNamespace(modified_count=1, upserted_id=None)
