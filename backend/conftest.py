import asyncio
import gc
import inspect
import sys

import pytest


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_pyfunc_call(pyfuncitem):
    yield
    _cleanup_backend_runtime_resources()


def pytest_runtest_teardown(item, nextitem):
    _cleanup_backend_runtime_resources()


def pytest_sessionfinish(session, exitstatus):
    _cleanup_backend_runtime_resources()


def _cleanup_backend_runtime_resources() -> None:
    loop = _current_available_loop()
    try:
        if loop is not None:
            loop.run_until_complete(_cleanup_backend_runtime_resources_async())
        else:
            asyncio.run(_cleanup_backend_runtime_resources_async())
    except Exception:
        pass
    gc.collect()


def _current_available_loop() -> asyncio.AbstractEventLoop | None:
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except (DeprecationWarning, RuntimeError):
        return None
    if loop.is_closed() or loop.is_running():
        return None
    return loop


async def _cleanup_backend_runtime_resources_async() -> None:
    await _drain_pending_tasks()
    _close_trader_config_manager_postgres_storage()
    _call_loaded_sync("trader.flows.cache", "close_cache")
    _call_loaded_sync("trader.config.databases", "close_database_manager")
    await _call_loaded_async("app.core.database", "close_database")
    await _call_loaded_async("app.core.redis", "close_redis")
    _call_loaded_sync("app.db.store.helpers", "close_sync_loop")
    await asyncio.sleep(0)
    await asyncio.sleep(0.05)
    await _drain_pending_tasks()


async def _drain_pending_tasks() -> None:
    current = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks() if task is not current and not task.done()
    ]
    if not pending:
        return

    _, remaining = await asyncio.wait(pending, timeout=5)
    for task in remaining:
        task.cancel()
    if remaining:
        await asyncio.gather(*remaining, return_exceptions=True)


async def _call_loaded_async(module_name: str, function_name: str) -> None:
    module = sys.modules.get(module_name)
    if module is None:
        return

    function = getattr(module, function_name, None)
    if function is None:
        return

    result = function()
    if inspect.isawaitable(result):
        await result


def _call_loaded_sync(module_name: str, function_name: str) -> None:
    module = sys.modules.get(module_name)
    if module is None:
        return

    function = getattr(module, function_name, None)
    if function is not None:
        function()


def _close_trader_config_manager_postgres_storage() -> None:
    for module_name in ("trader.config.manager", "trader.config.manager.runtime"):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        manager = getattr(module, "config_manager", None)
        if manager is None:
            continue
        close = getattr(manager, "close_postgres_storage", None)
        if close is not None:
            close()
