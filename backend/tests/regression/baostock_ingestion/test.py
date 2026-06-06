from __future__ import annotations

import importlib

import pytest


class FakeCollection:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.updates = []

    async def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))

    def find(self, query, projection=None):
        async def iterator():
            for row in self.rows:
                if _matches(row, query):
                    yield {key: row[key] for key in (projection or row) if key in row}

        return iterator()

    async def count_documents(self, query):
        return sum(1 for row in self.rows if _matches(row, query))

    async def find_one(self, query, *args, **kwargs):
        for row in self.rows:
            if _matches(row, query):
                return row
        return None


class FakeDB:
    def __init__(self, rows=None):
        self.stock_basic_info = FakeCollection(rows)
        self.market_quotes = FakeCollection([])


def _matches(row, query):
    if "$or" in query:
        return any(_matches(row, item) for item in query["$or"])
    return all(row.get(key) == value for key, value in query.items())


@pytest.mark.asyncio
async def test_baostock_basic_info_write_sets_source_aliases(monkeypatch):
    sync_module = importlib.import_module("app.worker.baostock.sync")
    monkeypatch.setattr(sync_module, "dual_write_hot_document", _noop_dual_write)

    service = sync_module.BaoStockSyncService.__new__(sync_module.BaoStockSyncService)
    service.db = FakeDB()

    await service._update_stock_basic_info({"code": "600519", "name": "贵州茅台"})

    query, update, upsert = service.db.stock_basic_info.updates[0]
    assert query == {"code": "600519", "source": "baostock"}
    assert upsert is True
    assert update["$set"]["source"] == "baostock"
    assert update["$set"]["data_source"] == "baostock"


@pytest.mark.asyncio
async def test_baostock_stock_pool_accepts_legacy_source_only_rows(monkeypatch):
    sync_module = importlib.import_module("app.worker.baostock.sync")

    service = sync_module.BaoStockSyncService.__new__(sync_module.BaoStockSyncService)
    service.db = FakeDB([{"code": "600519", "source": "baostock"}])

    rows = [
        row["code"]
        async for row in service.db.stock_basic_info.find(
            sync_module.BAOSTOCK_SOURCE_QUERY, {"code": 1}
        )
    ]

    assert rows == ["600519"]


async def _noop_dual_write(*args, **kwargs):
    return None
