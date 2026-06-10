from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

from app.core.network.proxy import ensure_cn_market_no_proxy


T = TypeVar("T")

_BAOSTOCK_LOCK = threading.RLock()


class BaoStockLoginError(RuntimeError):
    pass


@contextmanager
def baostock_session():
    """Open one serialized BaoStock login/query/logout session."""
    ensure_cn_market_no_proxy()
    bs = importlib.import_module("baostock")
    with _BAOSTOCK_LOCK:
        login_result = bs.login()
        if login_result.error_code != "0":
            raise BaoStockLoginError(f"baostock login failed: {login_result.error_msg}")
        try:
            yield bs
        finally:
            bs.logout()


def run_baostock_session(operation: Callable[[Any], T]) -> T:
    with baostock_session() as bs:
        return operation(bs)


async def run_baostock_session_async(
    operation: Callable[[Any], T],
    *,
    timeout: float,
) -> T:
    return await _run_in_daemon_thread(run_baostock_session, operation, timeout=timeout)


async def _run_in_daemon_thread(
    func: Callable[..., T],
    *args: Any,
    timeout: float,
    **kwargs: Any,
) -> T:
    """Run blocking BaoStock work without using asyncio's default executor."""
    future: concurrent.futures.Future[T] = concurrent.futures.Future()

    def worker() -> None:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
            return
        if not future.done():
            future.set_result(result)

    thread = threading.Thread(target=worker, name="baostock-session", daemon=True)
    thread.start()
    return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
