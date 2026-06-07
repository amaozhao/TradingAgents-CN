import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


@dataclass(frozen=True)
class PostgresSessionState:
    engine: AsyncEngine
    factory: async_sessionmaker[AsyncSession]
    database_url: str
    loop: asyncio.AbstractEventLoop


_session_states: dict[asyncio.AbstractEventLoop, PostgresSessionState] = {}


async def init_postgres(database_url: str | None = None) -> None:
    """Initialize the PostgreSQL async engine and session factory."""
    loop = asyncio.get_running_loop()
    resolved_url = database_url or settings.postgres_url
    state = _session_states.get(loop)

    if state is not None and state.database_url == resolved_url:
        return
    if state is not None:
        _session_states.pop(loop, None)
        await state.engine.dispose()

    engine = create_async_engine(
        resolved_url,
        pool_pre_ping=True,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
        pool_recycle=settings.POSTGRES_POOL_RECYCLE,
        echo=settings.POSTGRES_ECHO,
    )
    _session_states[loop] = PostgresSessionState(
        engine=engine,
        factory=async_sessionmaker(engine, expire_on_commit=False),
        database_url=resolved_url,
        loop=loop,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if len(_session_states) == 1:
            return next(iter(_session_states.values())).factory
        raise RuntimeError("PostgreSQL session factory is not initialized") from None

    state = _session_states.get(loop)
    if state is None:
        raise RuntimeError("PostgreSQL session factory is not initialized")
    return state.factory


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def close_postgres() -> None:
    """Dispose the PostgreSQL async engine and reset session state."""
    states = list(_session_states.values())
    _session_states.clear()

    for state in states:
        await _dispose_state(state)


def reset_postgres_state_for_tests() -> None:
    _session_states.clear()


async def _dispose_state(state: PostgresSessionState) -> None:
    current_loop = asyncio.get_running_loop()
    if state.loop is current_loop:
        await _dispose_engine_and_drain(state.engine)
        return

    if state.loop.is_closed():
        await _dispose_engine(state.engine, close=False)
        return

    if state.loop.is_running():
        await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(
                _dispose_engine_and_drain(state.engine), state.loop
            )
        )
        return

    await asyncio.to_thread(_dispose_state_on_owner_loop, state)


async def _dispose_engine_and_drain(engine: AsyncEngine, *, close: bool = True) -> None:
    await _dispose_engine(engine, close=close)
    await asyncio.sleep(0)
    await asyncio.sleep(0.01)


async def _dispose_engine(engine: AsyncEngine, *, close: bool = True) -> None:
    if close:
        await engine.dispose()
        return

    try:
        await engine.dispose(close=False)
    except TypeError:
        await engine.dispose()


def _dispose_state_on_owner_loop(state: PostgresSessionState) -> None:
    asyncio.set_event_loop(state.loop)
    try:
        state.loop.run_until_complete(_dispose_engine_and_drain(state.engine))
    finally:
        asyncio.set_event_loop(None)
