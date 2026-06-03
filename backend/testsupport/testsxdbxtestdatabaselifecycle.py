import pytest

from app.core import coredatabase as database


def test_postgres_runtime_enabled_uses_read_or_dual_write_flags(monkeypatch):
    monkeypatch.setattr(database.settings, "POSTGRES_READ_ENABLED", False)
    monkeypatch.setattr(database.settings, "POSTGRES_DUAL_WRITE_ENABLED", False)
    assert database.postgres_runtime_enabled() is False

    monkeypatch.setattr(database.settings, "POSTGRES_READ_ENABLED", True)
    assert database.postgres_runtime_enabled() is True

    monkeypatch.setattr(database.settings, "POSTGRES_READ_ENABLED", False)
    monkeypatch.setattr(database.settings, "POSTGRES_DUAL_WRITE_ENABLED", True)
    assert database.postgres_runtime_enabled() is True


@pytest.mark.asyncio
async def test_init_database_initializes_postgres_when_runtime_enabled(monkeypatch):
    calls = []

    async def fake_init_mongodb():
        database.db_manager.mongo_client = object()
        database.db_manager.mongo_db = object()
        calls.append("mongo")

    async def fake_init_redis():
        database.db_manager.redis_client = object()
        database.db_manager.redis_pool = object()
        calls.append("redis")

    async def fake_init_postgres_if_enabled():
        calls.append("postgres")

    async def fake_init_views():
        calls.append("views")

    monkeypatch.setattr(database.db_manager, "init_mongodb", fake_init_mongodb)
    monkeypatch.setattr(database.db_manager, "init_redis", fake_init_redis)
    monkeypatch.setattr(database, "init_postgres_if_enabled", fake_init_postgres_if_enabled)
    monkeypatch.setattr(database, "init_database_views_and_indexes", fake_init_views)

    await database.init_database()

    assert calls == ["mongo", "redis", "postgres", "views"]


@pytest.mark.asyncio
async def test_close_database_closes_postgres(monkeypatch):
    calls = []

    async def fake_close_connections():
        calls.append("mongo_redis")

    async def fake_close_postgres_if_enabled():
        calls.append("postgres")

    monkeypatch.setattr(database.db_manager, "close_connections", fake_close_connections)
    monkeypatch.setattr(database, "close_postgres_if_enabled", fake_close_postgres_if_enabled)

    await database.close_database()

    assert calls == ["mongo_redis", "postgres"]
