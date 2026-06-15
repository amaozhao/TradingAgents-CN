import pytest

from trader.flows.sources import (
    ChinaDataSource,
    DataSourceManager,
    USDataSource,
    USDataSourceManager,
)


def test_china_data_source_manager_constructor_does_not_use_sync_database(monkeypatch):
    import app.core.database as database

    calls: list[str] = []

    def sync_db_called():
        calls.append("sync")
        raise RuntimeError("force fallback")

    monkeypatch.setattr(database, "get_postgres_db_sync", sync_db_called)

    manager = DataSourceManager()

    assert calls == []
    assert manager.available_sources


class AsyncCursor:
    async def to_list(self, _length):
        return [
            {"data_source_name": "akshare", "priority": 9},
            {"data_source_name": "tushare", "priority": 5},
        ]


class AsyncCollection:
    def find(self, *_args, **_kwargs):
        return AsyncCursor()


class AsyncDb:
    datasource_groupings = AsyncCollection()


@pytest.mark.asyncio
async def test_china_data_source_manager_async_priority_order(monkeypatch):
    import trader.flows.sources as sources

    monkeypatch.setattr(sources, "get_postgres_db", lambda: AsyncDb(), raising=False)

    manager = DataSourceManager()
    manager.available_sources = [ChinaDataSource.TUSHARE, ChinaDataSource.AKSHARE]

    order = await manager.get_data_source_priority_order_async("600519")

    assert order == [ChinaDataSource.AKSHARE, ChinaDataSource.TUSHARE]


class ActiveConfigCollection:
    def __init__(self, document):
        self.document = document

    async def find_one(self, *_args, **_kwargs):
        return self.document


class ChinaConfigDb:
    def __init__(self):
        self.system_configs = ActiveConfigCollection(
            {
                "data_source_configs": [
                    {
                        "type": "tushare",
                        "name": "tushare",
                        "enabled": True,
                        "api_key": "db-token",
                    },
                    {"type": "akshare", "name": "akshare", "enabled": True},
                    {"type": "baostock", "name": "baostock", "enabled": False},
                ]
            }
        )


@pytest.mark.asyncio
async def test_china_data_source_manager_loads_available_sources_async(
    monkeypatch,
):
    import trader.flows.sources as sources

    original_import_module = sources.importlib.import_module

    def fake_import_module(name):
        if name in {"tushare", "akshare", "baostock"}:
            return object()
        return original_import_module(name)

    monkeypatch.setattr(sources.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(sources, "get_postgres_db", lambda: ChinaConfigDb(), raising=False)

    manager = DataSourceManager()
    manager.available_sources = []

    await manager.load_available_sources_async()

    assert manager.available_sources == [
        ChinaDataSource.TUSHARE,
        ChinaDataSource.AKSHARE,
    ]


class StockListCursor:
    async def to_list(self, _length):
        return [{"code": "000001", "name": "平安银行"}]


class StockListCollection:
    def find(self, *_args, **_kwargs):
        return StockListCursor()


class StockListDb:
    stock_basic_info = StockListCollection()


@pytest.mark.asyncio
async def test_china_data_source_manager_get_stock_basic_info_async_uses_async_cursor(
    monkeypatch,
):
    import trader.flows.sources as sources

    monkeypatch.setattr(sources, "get_postgres_db", lambda: StockListDb(), raising=False)

    manager = DataSourceManager()
    stocks = await manager.get_stock_basic_info_async()

    assert stocks == [{"code": "000001", "name": "平安银行"}]


@pytest.mark.asyncio
async def test_get_data_source_manager_async_loads_database_config(monkeypatch):
    import trader.flows.sources as sources

    class FakeManager:
        def __init__(self):
            self.loaded = False

        async def load_available_sources_async(self):
            self.loaded = True

    monkeypatch.setattr(sources, "_data_source_manager", None, raising=False)
    monkeypatch.setattr(sources, "DataSourceManager", FakeManager)

    manager = await sources.get_data_source_manager_async()
    cached = await sources.get_data_source_manager_async()

    assert manager.loaded is True
    assert cached is manager


def test_us_data_source_manager_constructor_does_not_use_sync_database(monkeypatch):
    import app.core.database as database

    calls: list[str] = []

    def sync_db_called():
        calls.append("sync")
        raise RuntimeError("force fallback")

    monkeypatch.setattr(database, "get_postgres_db_sync", sync_db_called)

    manager = USDataSourceManager()

    assert calls == []
    assert manager.available_sources


class USAsyncCursor:
    async def to_list(self, _length):
        return [
            {"data_source_name": "alpha_vantage", "priority": 8},
            {"data_source_name": "yfinance", "priority": 6},
        ]


class USAsyncCollection:
    def find(self, *_args, **_kwargs):
        return USAsyncCursor()


class USAsyncDb:
    datasource_groupings = USAsyncCollection()


@pytest.mark.asyncio
async def test_us_data_source_manager_async_priority_order(monkeypatch):
    import trader.flows.sources as sources

    monkeypatch.setattr(sources, "get_postgres_db", lambda: USAsyncDb(), raising=False)

    manager = USDataSourceManager()
    manager.available_sources = [
        USDataSource.YFINANCE,
        USDataSource.ALPHA_VANTAGE,
    ]

    order = await manager.get_data_source_priority_order_async("AAPL")

    assert order == [USDataSource.ALPHA_VANTAGE, USDataSource.YFINANCE]


class USConfigCollection:
    def find(self, *_args, **_kwargs):
        return USAsyncCursor()


class USConfigDb:
    datasource_groupings = USConfigCollection()
    system_configs = ActiveConfigCollection(
        {
            "data_source_configs": [
                {
                    "name": "alpha_vantage",
                    "type": "alpha_vantage",
                    "api_key": "db-alpha-key",
                },
                {
                    "name": "finnhub",
                    "type": "finnhub",
                    "api_key": "",
                },
            ]
        }
    )


@pytest.mark.asyncio
async def test_us_data_source_manager_loads_available_sources_async(monkeypatch):
    import trader.flows.sources as sources

    original_import_module = sources.importlib.import_module

    def fake_import_module(name):
        if name == "yfinance":
            return object()
        return original_import_module(name)

    monkeypatch.setattr(sources.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(sources, "get_postgres_db", lambda: USConfigDb(), raising=False)

    manager = USDataSourceManager()
    manager.use_postgres_cache = False
    manager.available_sources = []

    await manager.load_available_sources_async()

    assert manager.available_sources == [
        USDataSource.YFINANCE,
        USDataSource.ALPHA_VANTAGE,
    ]


@pytest.mark.asyncio
async def test_get_us_data_source_manager_async_loads_database_config(monkeypatch):
    import trader.flows.sources as sources

    class FakeUSManager:
        def __init__(self):
            self.loaded = False

        async def load_available_sources_async(self):
            self.loaded = True

    monkeypatch.setattr(sources, "_us_data_source_manager", None, raising=False)
    monkeypatch.setattr(sources, "USDataSourceManager", FakeUSManager)

    manager = await sources.get_us_data_source_manager_async()
    cached = await sources.get_us_data_source_manager_async()

    assert manager.loaded is True
    assert cached is manager
