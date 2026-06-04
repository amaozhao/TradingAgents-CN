import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest


def load_session_module() -> ModuleType:
    source_path = Path(__file__).resolve().parents[4] / "app" / "core" / "session.py"
    spec = importlib.util.spec_from_file_location("testedpostgressession", source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load session module from {source_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    previous_core = sys.modules.get("app.core")
    previous_config = sys.modules.get("app.core.config")
    core_module = ModuleType("app.core")
    config_module = ModuleType("app.core.config")
    setattr(
        config_module,
        "settings",
        SimpleNamespace(
            postgres_url="postgresql+asyncpg://u:p@localhost/db",
            POSTGRES_POOL_SIZE=5,
            POSTGRES_MAX_OVERFLOW=10,
            POSTGRES_POOL_TIMEOUT=30,
            POSTGRES_POOL_RECYCLE=1800,
            POSTGRES_ECHO=False,
        ),
    )
    setattr(core_module, "config", config_module)
    sys.modules["app.core"] = core_module
    sys.modules["app.core.config"] = config_module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_core is None:
            sys.modules.pop("app.core", None)
        else:
            sys.modules["app.core"] = previous_core
        if previous_config is None:
            sys.modules.pop("app.core.config", None)
        else:
            sys.modules["app.core.config"] = previous_config
    return module


db_session = load_session_module()


def test_session_factory_requires_initialization():
    db_session.reset_postgres_state_for_tests()

    with pytest.raises(
        RuntimeError, match="PostgreSQL session factory is not initialized"
    ):
        db_session.get_session_factory()


def test_init_postgres_keeps_session_factories_per_event_loop(monkeypatch):
    created_urls = []

    class FakeEngine:
        async def dispose(self):
            return None

    def fake_create_async_engine(url, **kwargs):
        created_urls.append((url, kwargs))
        return FakeEngine()

    class FakeSessionMaker:
        def __init__(self, engine, **kwargs):
            self.engine = engine
            self.kwargs = kwargs

    monkeypatch.setattr(db_session, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(db_session, "async_sessionmaker", FakeSessionMaker)

    async def init_and_get_factory():
        await db_session.init_postgres("postgresql+asyncpg://u:p@localhost/db")
        return db_session.get_session_factory()

    db_session.reset_postgres_state_for_tests()

    first_factory = asyncio.run(init_and_get_factory())
    second_factory = asyncio.run(init_and_get_factory())

    assert first_factory is not second_factory
    assert len(created_urls) == 2
    asyncio.run(db_session.close_postgres())


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
    with pytest.raises(
        RuntimeError, match="PostgreSQL session factory is not initialized"
    ):
        db_session.get_session_factory()
