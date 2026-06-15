from __future__ import annotations

from typing import Any

import pytest

from app.core import database
from app.db.store import helpers


async def _fake_value() -> dict[str, bool]:
    return {"ok": True}


@pytest.mark.asyncio
async def test_get_postgres_db_sync_rejects_async_runtime(monkeypatch):
    monkeypatch.delenv("TRADING_AGENTS_ALLOW_SYNC_DB_IN_ASYNC", raising=False)
    monkeypatch.delenv("TRADING_AGENTS_SYNC_DB_ASYNC_GUARD", raising=False)
    monkeypatch.setattr(database, "_sync_postgres_db", None)
    monkeypatch.setattr(database, "_sync_postgres_client", None)

    with pytest.raises(RuntimeError, match="get_postgres_db_sync"):
        database.get_postgres_db_sync()


@pytest.mark.asyncio
async def test_run_blocking_rejects_async_runtime(monkeypatch):
    monkeypatch.delenv("TRADING_AGENTS_ALLOW_SYNC_DB_IN_ASYNC", raising=False)
    monkeypatch.delenv("TRADING_AGENTS_SYNC_DB_ASYNC_GUARD", raising=False)

    coro = _fake_value()
    try:
        with pytest.raises(RuntimeError, match="_run_blocking"):
            helpers._run_blocking(coro)
    finally:
        coro.close()


@pytest.mark.asyncio
async def test_allow_sync_postgres_in_async_context_manager(monkeypatch):
    monkeypatch.delenv("TRADING_AGENTS_ALLOW_SYNC_DB_IN_ASYNC", raising=False)
    monkeypatch.delenv("TRADING_AGENTS_SYNC_DB_ASYNC_GUARD", raising=False)
    monkeypatch.setattr(helpers, "_get_sync_loop", lambda: FakeLoop())
    monkeypatch.setattr(
        helpers.asyncio, "run_coroutine_threadsafe", _fake_run_coroutine_threadsafe
    )

    with helpers.allow_sync_postgres_in_async("legacy-test"):
        assert helpers._run_blocking(_fake_value()) == {"ok": True}


@pytest.mark.asyncio
async def test_env_can_disable_async_guard(monkeypatch):
    monkeypatch.setenv("TRADING_AGENTS_ALLOW_SYNC_DB_IN_ASYNC", "1")
    monkeypatch.setattr(helpers, "_get_sync_loop", lambda: FakeLoop())
    monkeypatch.setattr(
        helpers.asyncio, "run_coroutine_threadsafe", _fake_run_coroutine_threadsafe
    )

    assert helpers._run_blocking(_fake_value()) == {"ok": True}


class FakeFuture:
    def result(self) -> dict[str, bool]:
        return {"ok": True}


class FakeLoop:
    pass


def _fake_run_coroutine_threadsafe(coro: Any, _loop: FakeLoop) -> FakeFuture:
    coro.close()
    return FakeFuture()
