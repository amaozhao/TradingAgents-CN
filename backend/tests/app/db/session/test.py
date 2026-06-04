from typing import Any, cast

import pytest

from app.db import session as db_session


def test_session_factory_requires_initialization():
    db_session.reset_postgres_state_for_tests()

    with pytest.raises(RuntimeError, match="PostgreSQL session factory is not initialized"):
        db_session.get_session_factory()


@pytest.mark.asyncio
async def test_init_and_dispose_postgres_engine(monkeypatch):
    created_urls = []
    disposed = False

    class FakeEngine:
        async def dispose(self):
            nonlocal disposed
            disposed = True

    def fake_create_async_engine(url, **kwargs):
        created_urls.append((url, kwargs))
        return FakeEngine()

    class FakeSessionMaker:
        def __init__(self, engine, **kwargs):
            self.engine = engine
            self.kwargs = kwargs

    monkeypatch.setattr(db_session, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(db_session, "async_sessionmaker", FakeSessionMaker)

    db_session.reset_postgres_state_for_tests()
    await db_session.init_postgres("postgresql+asyncpg://u:p@localhost/db")

    factory = cast(Any, db_session.get_session_factory())

    assert created_urls[0][0] == "postgresql+asyncpg://u:p@localhost/db"
    assert created_urls[0][1]["pool_pre_ping"] is True
    assert factory.kwargs["expire_on_commit"] is False

    await db_session.close_postgres()

    assert disposed is True
    with pytest.raises(RuntimeError, match="PostgreSQL session factory is not initialized"):
        db_session.get_session_factory()
