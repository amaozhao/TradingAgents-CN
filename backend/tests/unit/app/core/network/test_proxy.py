from __future__ import annotations

import os

from app.core.network.proxy import configure_runtime_proxy, ensure_cn_market_no_proxy


def test_configure_runtime_proxy_normalizes_backend_proxy_to_7897(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7899")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7899")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:7899")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.delenv("TRADING_AGENTS_PROXY_URL", raising=False)
    monkeypatch.delenv("TRADING_AGENTS_PROXY_PORT", raising=False)

    result = configure_runtime_proxy()

    assert result["proxy_url"] == "http://127.0.0.1:7897"
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:7897"
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:7897"
    assert os.environ["ALL_PROXY"] == "http://127.0.0.1:7897"
    assert os.environ["CLASH_MIXED_PORT"] == "7897"
    assert "eastmoney.com" in os.environ["NO_PROXY"]
    assert "api.tushare.pro" in os.environ["NO_PROXY"]
    assert "baostock.com" in os.environ["NO_PROXY"]
    assert "api.minimaxi.com" in os.environ["NO_PROXY"]
    assert "api.deepseek.com" in os.environ["NO_PROXY"]
    assert "api.openai.com" not in os.environ["NO_PROXY"]
    assert "api.anthropic.com" not in os.environ["NO_PROXY"]
    assert "generativelanguage.googleapis.com" not in os.environ["NO_PROXY"]


def test_configure_runtime_proxy_accepts_project_direct_hosts(monkeypatch):
    monkeypatch.setenv("TRADING_AGENTS_DIRECT_HOSTS", "dashscope.aliyuncs.com,open.bigmodel.cn")
    monkeypatch.delenv("NO_PROXY", raising=False)

    result = configure_runtime_proxy()

    assert "dashscope.aliyuncs.com" in result["no_proxy"]
    assert "open.bigmodel.cn" in result["no_proxy"]


def test_ensure_cn_market_no_proxy_preserves_current_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("NO_PROXY", "localhost")

    entries = ensure_cn_market_no_proxy()

    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:7897"
    assert entries[0] == "localhost"
    assert "push2his.eastmoney.com" in entries
    assert "www.baostock.com" in entries
