from types import SimpleNamespace

import pytest

import app.routers.stocks as stocks


@pytest.mark.asyncio
async def test_new_data_source_manager_async_loads_priority(monkeypatch):
    calls: list[str] = []

    class FakeManager:
        async def load_priority_from_database_async(self):
            calls.append("loaded")

    original_import_module = stocks.importlib.import_module

    def fake_import_module(name):
        if name == "app.services.sources.manager":
            return SimpleNamespace(DataSourceManager=FakeManager)
        return original_import_module(name)

    monkeypatch.setattr(stocks.importlib, "import_module", fake_import_module)

    manager = await stocks._new_data_source_manager_async()

    assert isinstance(manager, FakeManager)
    assert calls == ["loaded"]
