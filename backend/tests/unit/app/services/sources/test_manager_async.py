import pytest

from app.services.sources import manager as manager_module
from app.services.sources.manager import DataSourceManager


class AsyncCursor:
    async def to_list(self, _length):
        return [
            {
                "data_source_name": "akshare",
                "priority": 9,
                "enabled": True,
            }
        ]


class AsyncCollection:
    def find(self, *_args, **_kwargs):
        return AsyncCursor()


class AsyncDb:
    datasource_groupings = AsyncCollection()


class FakeAdapter:
    def __init__(self, name: str, priority: int = 1) -> None:
        self.name = name
        self._priority = priority
        self.async_checked = False

    @property
    def priority(self) -> int:
        return self._priority

    def _get_default_priority(self) -> int:
        return 1

    def is_available(self) -> bool:
        return True

    async def is_available_async(self) -> bool:
        self.async_checked = True
        return True


class AsyncOnlyAdapter(FakeAdapter):
    def is_available(self) -> bool:
        raise AssertionError("async runtime must not call sync availability")


def install_fake_adapters(monkeypatch):
    monkeypatch.setattr(manager_module, "TushareAdapter", lambda: FakeAdapter("tushare"))
    monkeypatch.setattr(manager_module, "AKShareAdapter", lambda: FakeAdapter("akshare"))
    monkeypatch.setattr(manager_module, "BaoStockAdapter", lambda: FakeAdapter("baostock"))


def test_data_source_manager_constructor_does_not_use_sync_database(monkeypatch):
    from app.core import database

    install_fake_adapters(monkeypatch)
    calls: list[str] = []

    def sync_db_called():
        calls.append("sync")
        raise RuntimeError("force default priorities")

    monkeypatch.setattr(database, "get_postgres_db_sync", sync_db_called)

    manager = DataSourceManager()

    assert calls == []
    assert manager.adapters


@pytest.mark.asyncio
async def test_async_priority_loader_uses_async_database(monkeypatch):
    install_fake_adapters(monkeypatch)
    monkeypatch.setattr(manager_module, "get_postgres_db", lambda: AsyncDb())

    manager = DataSourceManager()
    await manager.load_priority_from_database_async()

    priorities = {adapter.name: adapter.priority for adapter in manager.adapters}
    assert priorities["akshare"] == 9


@pytest.mark.asyncio
async def test_get_available_adapters_async_uses_async_availability(monkeypatch):
    monkeypatch.setattr(manager_module, "TushareAdapter", lambda: AsyncOnlyAdapter("tushare"))
    monkeypatch.setattr(manager_module, "AKShareAdapter", lambda: AsyncOnlyAdapter("akshare"))
    monkeypatch.setattr(manager_module, "BaoStockAdapter", lambda: AsyncOnlyAdapter("baostock"))

    manager = DataSourceManager()
    adapters = await manager.get_available_adapters_async()

    assert [adapter.name for adapter in adapters] == ["tushare", "akshare", "baostock"]
    assert all(adapter.async_checked for adapter in adapters)


def test_tushare_adapter_does_not_auto_connect_provider(monkeypatch):
    from app.services.sources import tushare as tushare_module

    calls: list[bool] = []

    class FakeProvider:
        connected = False
        api = None

    class FakeModule:
        @staticmethod
        def get_tushare_provider(auto_connect=True):
            calls.append(auto_connect)
            return FakeProvider()

    monkeypatch.setattr(
        tushare_module.importlib,
        "import_module",
        lambda name: FakeModule
        if name == "trader.flows.providers.china.tushare"
        else manager_module.importlib.import_module(name),
    )

    adapter = tushare_module.TushareAdapter()

    assert adapter._provider is not None
    assert calls == [False]
