from __future__ import annotations

import asyncio

import pytest

from app.db.store.cursor import PostgresCursor
from app.db.store.sync import SyncPostgresCollection


class FakeAsyncCollection:
    async def find_one(self, query):
        return {"query": query}


def test_sync_collection_uses_blocking_bridge(monkeypatch):
    calls = []

    def fake_run_blocking(coro):
        calls.append(coro)
        coro.close()
        return {"ok": True}

    monkeypatch.setattr("app.db.store.sync._run_blocking", fake_run_blocking)

    collection = SyncPostgresCollection(FakeAsyncCollection())

    assert collection.find_one({"name": "demo"}) == {"ok": True}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_sync_loop_is_separate_from_running_loop():
    from app.db.store.helpers import _get_sync_loop

    current_loop = asyncio.get_running_loop()
    sync_loop = _get_sync_loop()

    assert sync_loop is not current_loop
    assert sync_loop.is_running()


def test_cursor_sync_iteration_uses_blocking_bridge(monkeypatch):
    calls = []

    def fake_run_blocking(coro):
        calls.append(coro)
        coro.close()
        return [{"name": "demo"}]

    monkeypatch.setattr("app.db.store.cursor._run_blocking", fake_run_blocking)

    cursor = PostgresCursor(loader=lambda: _load_documents())

    assert list(cursor) == [{"name": "demo"}]
    assert len(calls) == 1


async def _load_documents():
    return [{"name": "demo"}]
