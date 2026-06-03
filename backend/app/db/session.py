from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.coreconfig import settings

_postgres_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_postgres(database_url: str | None = None) -> None:
    """Initialize the PostgreSQL async engine and session factory."""
    global _postgres_engine, _session_factory

    if _postgres_engine is not None:
        return

    _postgres_engine = create_async_engine(
        database_url or settings.POSTGRES_URL,
        pool_pre_ping=True,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
        pool_recycle=settings.POSTGRES_POOL_RECYCLE,
        echo=settings.POSTGRES_ECHO,
    )
    _session_factory = async_sessionmaker(_postgres_engine, expire_on_commit=False)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("PostgreSQL session factory is not initialized")
    return _session_factory


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def close_postgres() -> None:
    """Dispose the PostgreSQL async engine and reset session state."""
    global _postgres_engine, _session_factory

    engine = _postgres_engine
    _postgres_engine = None
    _session_factory = None

    if engine is not None:
        await engine.dispose()


def reset_postgres_state_for_tests() -> None:
    global _postgres_engine, _session_factory

    _postgres_engine = None
    _session_factory = None
