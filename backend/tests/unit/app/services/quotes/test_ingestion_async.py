import pytest

from app.services.quotes import ingestion
from app.services.quotes.ingestion import QuotesIngestionService


@pytest.mark.asyncio
async def test_new_data_source_manager_async_loads_priority(monkeypatch):
    calls: list[str] = []

    class FakeManager:
        async def load_priority_from_database_async(self):
            calls.append("loaded")

    monkeypatch.setattr(ingestion, "DataSourceManager", FakeManager)

    service = QuotesIngestionService()
    manager = await service._new_data_source_manager_async()

    assert isinstance(manager, FakeManager)
    assert calls == ["loaded"]


@pytest.mark.asyncio
async def test_backfill_last_close_snapshot_uses_loaded_source_manager(monkeypatch):
    writes: list[tuple[dict, str, str]] = []

    class FakeManager:
        def __init__(self):
            self.loaded = False

        async def load_priority_from_database_async(self):
            self.loaded = True

        def get_realtime_quotes_with_fallback(self):
            assert self.loaded is True
            return {"000001": {"close": 10.0}}, "fake_source"

        def find_latest_trade_date_with_fallback(self):
            assert self.loaded is True
            return "20260615"

    async def fake_bulk_upsert(quotes_map, trade_date, source):
        writes.append((quotes_map, trade_date, source))

    monkeypatch.setattr(ingestion, "DataSourceManager", FakeManager)

    service = QuotesIngestionService()
    monkeypatch.setattr(service, "_bulk_upsert", fake_bulk_upsert)

    await service.backfill_last_close_snapshot()

    assert writes == [({"000001": {"close": 10.0}}, "20260615", "fake_source")]
