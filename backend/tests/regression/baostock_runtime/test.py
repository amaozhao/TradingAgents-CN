from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

import pytest

from app.core import baostock_runtime


class FakeLoginResult:
    error_code = "0"
    error_msg = ""


class FakeBaoStock:
    def __init__(self) -> None:
        self.events: list[str] = []

    def login(self) -> FakeLoginResult:
        self.events.append("login")
        return FakeLoginResult()

    def logout(self) -> None:
        self.events.append("logout")


def test_baostock_session_logs_in_and_out_with_no_proxy(monkeypatch):
    fake_bs = FakeBaoStock()
    monkeypatch.setitem(sys.modules, "baostock", fake_bs)
    monkeypatch.setenv("NO_PROXY", "localhost")

    def query(bs: Any) -> str:
        bs.events.append("query")
        return "ok"

    result = baostock_runtime.run_baostock_session(query)

    assert result == "ok"
    assert fake_bs.events == ["login", "query", "logout"]
    assert "baostock.com" in os.environ["NO_PROXY"]
    assert "api.tushare.pro" in os.environ["NO_PROXY"]


def test_baostock_sessions_are_serialized(monkeypatch):
    fake_bs = FakeBaoStock()
    monkeypatch.setitem(sys.modules, "baostock", fake_bs)
    active = 0
    max_active = 0
    results: list[str] = []

    def query(_bs: Any) -> str:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        time.sleep(0.02)
        active -= 1
        return "ok"

    threads = [
        threading.Thread(target=lambda: results.append(baostock_runtime.run_baostock_session(query))),
        threading.Thread(target=lambda: results.append(baostock_runtime.run_baostock_session(query))),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert sorted(results) == ["ok", "ok"]
    assert max_active == 1
    assert fake_bs.events == ["login", "logout", "login", "logout"]


@pytest.mark.asyncio
async def test_baostock_async_session_returns_without_default_executor(monkeypatch):
    fake_bs = FakeBaoStock()
    monkeypatch.setitem(sys.modules, "baostock", fake_bs)

    def query(_bs: Any) -> str:
        return threading.current_thread().name

    thread_name = await baostock_runtime.run_baostock_session_async(query, timeout=1)

    assert thread_name == "baostock-session"
    assert fake_bs.events == ["login", "logout"]


def test_baostock_session_logs_out_after_query_error(monkeypatch):
    fake_bs = FakeBaoStock()
    monkeypatch.setitem(sys.modules, "baostock", fake_bs)

    def query(_bs: Any) -> None:
        raise RuntimeError("query failed")

    with pytest.raises(RuntimeError, match="query failed"):
        baostock_runtime.run_baostock_session(query)

    assert fake_bs.events == ["login", "logout"]
