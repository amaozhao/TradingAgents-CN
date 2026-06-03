from datetime import datetime, timedelta
from types import SimpleNamespace
import sys

import pytest

from app.worker import (
    akshare_sync_service,
    baostock_init_service,
    baostock_sync_service,
    example_sdk_sync_service,
    hk_data_service,
    hk_sync_service,
    tushare_sync_service,
    us_data_service,
    us_sync_service,
)


@pytest.mark.asyncio
async def test_us_basic_info_bulk_write_dual_writes_postgres(monkeypatch):
    service = us_sync_service.USSyncService.__new__(us_sync_service.USSyncService)
    service.db = SimpleNamespace(stock_basic_info_us=FakeCollection())
    service.yfinance_provider = SimpleNamespace(
        get_stock_info=lambda _code: {
            "shortName": "Apple",
            "longName": "Apple Inc.",
            "currency": "USD",
            "exchange": "NASDAQ",
            "country": "US",
            "marketCap": 3000000000000,
            "industry": "Consumer Electronics",
        }
    )
    service._stock_list_cache_time = None
    service._get_us_stock_list_from_finnhub = lambda: ["AAPL", "MSFT"]

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(us_sync_service, "dual_write_hot_documents", fake_dual_write)

    result = await service.sync_basic_info_from_source()

    assert result == {"updated": 2, "inserted": 0, "failed": 0}
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert [doc["code"] for doc in dual_write_calls[0][1]] == ["AAPL", "MSFT"]
    assert all(doc["source"] == "yfinance" for doc in dual_write_calls[0][1])


@pytest.mark.asyncio
async def test_us_quotes_bulk_write_dual_writes_postgres(monkeypatch):
    service = us_sync_service.USSyncService.__new__(us_sync_service.USSyncService)
    service.db = SimpleNamespace(market_quotes_us=FakeCollection())
    service.us_stock_list = ["AAPL", "MSFT"]

    monkeypatch.setitem(
        __import__("sys").modules,
        "yfinance",
        SimpleNamespace(Ticker=lambda _code: SimpleNamespace(history=lambda period: FakeHistory())),
    )

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(us_sync_service, "dual_write_hot_documents", fake_dual_write)

    result = await service.sync_quotes_from_source()

    assert result == {"updated": 2, "inserted": 0, "failed": 0}
    assert dual_write_calls[0][0] == "market_quotes"
    assert [doc["code"] for doc in dual_write_calls[0][1]] == ["AAPL", "MSFT"]
    assert all(doc["source"] == "yfinance" for doc in dual_write_calls[0][1])


@pytest.mark.asyncio
async def test_hk_basic_info_bulk_write_dual_writes_postgres(monkeypatch):
    service = hk_sync_service.HKDataService.__new__(hk_sync_service.HKDataService)
    service.db = SimpleNamespace(stock_basic_info_hk=FakeCollection())
    service.providers = {
        "yfinance": SimpleNamespace(
            get_stock_info=lambda _code: {
                "name": "Tencent",
                "name_en": "Tencent Holdings",
                "currency": "HKD",
                "exchange": "HKG",
                "market_cap": 3000000000000,
                "industry": "Internet",
            }
        )
    }
    service._stock_list_cache_time = None
    service._get_hk_stock_list_from_akshare = lambda: ["00700", "09988"]

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(hk_sync_service, "dual_write_hot_documents", fake_dual_write)

    result = await service.sync_basic_info_from_source("yfinance")

    assert result == {"updated": 2, "inserted": 0, "failed": 0}
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert [doc["code"] for doc in dual_write_calls[0][1]] == ["00700", "09988"]
    assert all(doc["source"] == "yfinance" for doc in dual_write_calls[0][1])


@pytest.mark.asyncio
async def test_hk_akshare_batch_basic_info_dual_writes_postgres(monkeypatch):
    service = hk_sync_service.HKDataService.__new__(hk_sync_service.HKDataService)
    service.db = SimpleNamespace(stock_basic_info_hk=FakeCollection())

    monkeypatch.setitem(
        __import__("sys").modules,
        "akshare",
        SimpleNamespace(stock_hk_spot=lambda: FakeHKSpotFrame()),
    )

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(hk_sync_service, "dual_write_hot_documents", fake_dual_write)

    result = await service._sync_basic_info_from_akshare_batch()

    assert result == {"updated": 2, "inserted": 0, "failed": 0}
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert [doc["code"] for doc in dual_write_calls[0][1]] == ["00700", "09988"]
    assert all(doc["source"] == "akshare" for doc in dual_write_calls[0][1])


@pytest.mark.asyncio
async def test_hk_quotes_bulk_write_dual_writes_postgres(monkeypatch):
    service = hk_sync_service.HKDataService.__new__(hk_sync_service.HKDataService)
    service.db = SimpleNamespace(market_quotes_hk=FakeCollection())
    service.hk_stock_list = ["00700", "09988"]
    service.providers = {
        "yfinance": SimpleNamespace(
            get_real_time_price=lambda _code: {
                "price": 390,
                "open": 380,
                "high": 395,
                "low": 375,
                "volume": 123456,
            }
        )
    }

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(hk_sync_service, "dual_write_hot_documents", fake_dual_write)

    result = await service.sync_quotes_from_source("yfinance")

    assert result == {"updated": 2, "inserted": 0, "failed": 0}
    assert dual_write_calls[0][0] == "market_quotes"
    assert [doc["code"] for doc in dual_write_calls[0][1]] == ["00700", "09988"]
    assert all(doc["source"] == "yfinance" for doc in dual_write_calls[0][1])


@pytest.mark.asyncio
async def test_baostock_basic_info_update_dual_writes_postgres(monkeypatch):
    service = baostock_sync_service.BaoStockSyncService.__new__(baostock_sync_service.BaoStockSyncService)
    service.db = SimpleNamespace(stock_basic_info=FakeUpdateCollection())

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(baostock_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._update_stock_basic_info({"code": "000001", "name": "平安银行"})

    assert dual_write_calls == [
        (
            "stock_basic_info",
            {"code": "000001", "name": "平安银行", "symbol": "000001", "source": "baostock"},
        )
    ]


@pytest.mark.asyncio
async def test_baostock_quotes_update_dual_writes_postgres(monkeypatch):
    service = baostock_sync_service.BaoStockSyncService.__new__(baostock_sync_service.BaoStockSyncService)
    service.db = SimpleNamespace(market_quotes=FakeUpdateCollection())

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(baostock_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._update_stock_quotes({"code": "000001", "close": 10.2})

    assert dual_write_calls == [
        (
            "market_quotes",
            {"code": "000001", "close": 10.2, "symbol": "000001", "source": "baostock"},
        )
    ]


@pytest.mark.asyncio
async def test_akshare_batch_quotes_dual_writes_postgres(monkeypatch):
    service = akshare_sync_service.AKShareSyncService.__new__(akshare_sync_service.AKShareSyncService)
    service.db = SimpleNamespace(market_quotes=FakeUpdateCollection())

    class FakeProvider:
        async def get_batch_stock_quotes(self, _batch):
            return {"000001": {"close": 10.2}}

    service.provider = FakeProvider()

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(akshare_sync_service, "dual_write_hot_document", fake_dual_write)

    result = await service._process_quotes_batch(["000001"])

    assert result == {"success_count": 1, "error_count": 0, "errors": []}
    assert dual_write_calls == [
        (
            "market_quotes",
            {"close": 10.2, "symbol": "000001", "code": "000001", "source": "akshare"},
        )
    ]


@pytest.mark.asyncio
async def test_baostock_historical_metadata_dual_writes_postgres(monkeypatch):
    service = baostock_sync_service.BaoStockSyncService.__new__(baostock_sync_service.BaoStockSyncService)
    service.db = SimpleNamespace(market_quotes=FakeUpdateCollection())
    service.historical_service = SimpleNamespace(save_historical_data=fake_save_historical_data)

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(baostock_sync_service, "dual_write_hot_document", fake_dual_write)

    assert await service._update_historical_data("000001", FakeHistoricalFrame(), period="daily") == 3
    assert dual_write_calls[0][0] == "market_quotes"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["source"] == "baostock"
    assert dual_write_calls[0][1]["historical_records_count"] == 3


@pytest.mark.asyncio
async def test_example_sdk_financial_update_dual_writes_postgres(monkeypatch):
    service = example_sdk_sync_service.ExampleSDKSyncService.__new__(
        example_sdk_sync_service.ExampleSDKSyncService
    )

    class FakeProvider:
        async def get_financial_data(self, _code):
            return {"report_period": "2025Q4", "roe": 12.3}

    service.provider = FakeProvider()
    service.sync_stats = {"financial": {"total": 0, "success": 0, "failed": 0}}

    fake_db = SimpleNamespace(stock_financial_data=FakeUpdateCollection())
    monkeypatch.setattr(example_sdk_sync_service, "get_mongo_db", lambda: fake_db)

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(example_sdk_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._process_financial_data("000001")

    assert service.sync_stats["financial"]["success"] == 1
    assert dual_write_calls[0][0] == "stock_financial_data"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["data_source"] == "example_sdk"
    assert dual_write_calls[0][1]["report_period"] == "2025Q4"


@pytest.mark.asyncio
async def test_example_sdk_sync_status_dual_writes_postgres(monkeypatch):
    service = example_sdk_sync_service.ExampleSDKSyncService.__new__(
        example_sdk_sync_service.ExampleSDKSyncService
    )
    service.sync_stats = {"basic": {"success": 1}}

    fake_db = SimpleNamespace(sync_status=FakeUpdateCollection())
    monkeypatch.setattr(example_sdk_sync_service, "get_mongo_db", lambda: fake_db)

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(example_sdk_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._record_sync_status("completed", start_time=datetime.now() - timedelta(seconds=1))

    assert dual_write_calls[0][0] == "sync_status"
    assert dual_write_calls[0][1]["job"] == "example_sdk_sync"
    assert dual_write_calls[0][1]["status"] == "completed"


@pytest.mark.asyncio
async def test_tushare_scheduler_progress_dual_writes_postgres(monkeypatch):
    service = tushare_sync_service.TushareSyncService.__new__(tushare_sync_service.TushareSyncService)
    fake_collection = FakeSchedulerExecutionCollection(
        {
            "_id": "scheduler-1",
            "job_id": "tushare_daily",
            "status": "running",
            "progress": 20,
            "timestamp": datetime(2026, 6, 3),
        }
    )

    monkeypatch.setitem(
        sys.modules,
        "pymongo",
        SimpleNamespace(MongoClient=lambda _uri: FakeMongoClient(fake_collection)),
    )

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(tushare_sync_service, "dual_write_hot_document", fake_dual_write)

    await service._update_progress("tushare_daily", 55, "同步行情")

    assert fake_collection.updates[0][0] == {"_id": "scheduler-1"}
    assert dual_write_calls[0][0] == "scheduler_executions"
    assert dual_write_calls[0][1]["_id"] == "scheduler-1"
    assert dual_write_calls[0][1]["job_id"] == "tushare_daily"
    assert dual_write_calls[0][1]["progress"] == 55
    assert dual_write_calls[0][1]["progress_message"] == "同步行情"


@pytest.mark.asyncio
async def test_hk_on_demand_cache_dual_writes_postgres(monkeypatch):
    service = hk_data_service.HKDataService.__new__(hk_data_service.HKDataService)
    service.db = SimpleNamespace(stock_basic_info_hk=FakeUpdateCollection())

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(hk_data_service, "dual_write_hot_document", fake_dual_write)

    await service._save_to_cache({"code": "00700", "source": "yfinance", "name": "Tencent"})

    assert dual_write_calls == [
        ("stock_basic_info", {"code": "00700", "source": "yfinance", "name": "Tencent"})
    ]


@pytest.mark.asyncio
async def test_us_on_demand_cache_dual_writes_postgres(monkeypatch):
    service = us_data_service.USDataService.__new__(us_data_service.USDataService)
    service.db = SimpleNamespace(stock_basic_info_us=FakeUpdateCollection())

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(us_data_service, "dual_write_hot_document", fake_dual_write)

    await service._save_to_cache({"code": "AAPL", "source": "yfinance", "name": "Apple"})

    assert dual_write_calls == [
        ("stock_basic_info", {"code": "AAPL", "source": "yfinance", "name": "Apple"})
    ]


@pytest.mark.asyncio
async def test_baostock_init_financial_update_dual_writes_postgres(monkeypatch):
    service = baostock_init_service.BaoStockInitService.__new__(
        baostock_init_service.BaoStockInitService
    )
    service.db = SimpleNamespace(stock_basic_info=FakeFindUpdateCollection([{"code": "000001"}]))

    class FakeProvider:
        async def get_financial_data(self, _code):
            return {"roe": 11.2}

    service.sync_service = SimpleNamespace(provider=FakeProvider())

    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(baostock_init_service, "dual_write_hot_document", fake_dual_write)

    assert await service._sync_financial_data() == 1
    assert dual_write_calls[0][0] == "stock_basic_info"
    assert dual_write_calls[0][1]["code"] == "000001"
    assert dual_write_calls[0][1]["source"] == "baostock"
    assert dual_write_calls[0][1]["financial_data"] == {"roe": 11.2}


class FakeCollection:
    async def bulk_write(self, operations):
        return SimpleNamespace(modified_count=len(operations), upserted_count=0)


class FakeUpdateCollection:
    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)


class FakeFindUpdateCollection(FakeUpdateCollection):
    def __init__(self, documents):
        self.documents = documents

    def find(self, *_args, **_kwargs):
        return FakeAsyncCursor(self.documents)


class FakeSchedulerExecutionCollection:
    def __init__(self, document):
        self.document = document
        self.updates = []

    def find_one(self, *_args, **_kwargs):
        return self.document

    def update_one(self, *args, **kwargs):
        self.updates.append((args[0], args[1], kwargs))
        return SimpleNamespace(matched_count=1, modified_count=1)


class FakeMongoClient:
    def __init__(self, scheduler_collection):
        self.scheduler_collection = scheduler_collection
        self.closed = False

    def __getitem__(self, _name):
        return SimpleNamespace(scheduler_executions=self.scheduler_collection)

    def close(self):
        self.closed = True


class FakeAsyncCursor:
    def __init__(self, documents):
        self._documents = iter(documents)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._documents)
        except StopIteration:
            raise StopAsyncIteration


class FakeHistory:
    empty = False

    @property
    def iloc(self):
        return self

    def __getitem__(self, _index):
        return {
            "Close": 190.0,
            "Open": 180.0,
            "High": 195.0,
            "Low": 175.0,
            "Volume": 123456,
        }


class FakeHistoricalFrame:
    empty = False

    @property
    def iloc(self):
        return self

    def __getitem__(self, _index):
        return {"date": "2025-01-01"}


async def fake_save_historical_data(**_kwargs):
    return 3


class FakeHKSpotFrame:
    empty = False

    def __len__(self):
        return 2

    def iterrows(self):
        yield 0, {
            "代码": "700",
            "中文名称": "腾讯控股",
            "最新价": 390,
            "涨跌幅": 1.2,
            "总市值": 3000000000000,
            "市盈率": 20,
        }
        yield 1, {
            "代码": "9988",
            "中文名称": "阿里巴巴",
            "最新价": 80,
            "涨跌幅": 0.5,
            "总市值": 2000000000000,
            "市盈率": 18,
        }
