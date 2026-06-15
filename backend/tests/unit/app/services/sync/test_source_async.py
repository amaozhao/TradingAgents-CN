from types import SimpleNamespace

import pytest

from app.services.sync import source as sync_source


@pytest.mark.asyncio
async def test_run_full_sync_loads_source_priority_before_use(monkeypatch):
    calls: list[str] = []

    class FakeManager:
        def __init__(self):
            self.loaded = False

        async def load_priority_from_database_async(self):
            self.loaded = True
            calls.append("loaded")

        def get_available_adapters(self):
            raise AssertionError("async sync service must not call sync availability")

        async def get_available_adapters_async(self):
            assert self.loaded is True, "manager priority not loaded"
            return []

    original_import_module = sync_source.importlib.import_module

    def fake_import_module(name):
        if name == "app.services.sources.manager":
            return SimpleNamespace(DataSourceManager=FakeManager)
        return original_import_module(name)

    async def fake_db():
        return object()

    async def fake_persist(_db, _stats):
        return None

    monkeypatch.setattr(sync_source.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(sync_source, "_get_initialized_postgres_db", fake_db)

    service = sync_source.MultiSourceBasicsSyncService()
    monkeypatch.setattr(service, "_persist_status", fake_persist)

    result = await service.run_full_sync(force=True)

    assert calls == ["loaded"]
    assert result["status"] == "failed"
    assert result["message"] == "No available data sources found"
