from __future__ import annotations

import os
from typing import Any


DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = "7897"

BASE_NO_PROXY_HOSTS = (
    "localhost",
    "127.0.0.1",
    "::1",
    "*.local",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)

A_SHARE_NO_PROXY_HOSTS = (
    "eastmoney.com",
    ".eastmoney.com",
    "push2.eastmoney.com",
    "push2his.eastmoney.com",
    "82.push2.eastmoney.com",
    "82.push2delay.eastmoney.com",
    "gtimg.cn",
    ".gtimg.cn",
    "sina.com.cn",
    ".sina.com.cn",
    "api.tushare.pro",
    "tushare.pro",
    ".tushare.pro",
    "waditu.com",
    ".waditu.com",
    "baostock.com",
    ".baostock.com",
    "www.baostock.com",
)

DIRECT_LLM_NO_PROXY_HOSTS = (
    "api.minimaxi.com",
    "platform.minimaxi.com",
    "minimaxi.com",
    ".minimaxi.com",
    "api.deepseek.com",
    "platform.deepseek.com",
    "deepseek.com",
    ".deepseek.com",
)


def configure_runtime_proxy(
    *,
    proxy_host: str | None = None,
    proxy_port: str | int | None = None,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    """Normalize backend proxy env while keeping A-share data sources direct."""
    host = proxy_host or os.environ.get("TRADING_AGENTS_PROXY_HOST") or DEFAULT_PROXY_HOST
    port = str(proxy_port or os.environ.get("TRADING_AGENTS_PROXY_PORT") or DEFAULT_PROXY_PORT)
    url = proxy_url or os.environ.get("TRADING_AGENTS_PROXY_URL") or f"http://{host}:{port}"

    for key in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        os.environ[key] = url
    for key in ("ws_proxy", "wss_proxy", "WS_PROXY", "WSS_PROXY"):
        os.environ[key] = url

    os.environ["CLASH_PROXY_HOST"] = host
    os.environ["CLASH_MIXED_PORT"] = port

    direct_hosts = _configured_direct_hosts()
    no_proxy_entries = ensure_no_proxy(
        (*BASE_NO_PROXY_HOSTS, *A_SHARE_NO_PROXY_HOSTS, *DIRECT_LLM_NO_PROXY_HOSTS, *direct_hosts)
    )
    os.environ["CLASH_NO_PROXY"] = ",".join(no_proxy_entries)
    return {"proxy_url": url, "proxy_host": host, "proxy_port": port, "no_proxy": no_proxy_entries}


def ensure_cn_market_no_proxy() -> list[str]:
    return ensure_no_proxy(A_SHARE_NO_PROXY_HOSTS)


def ensure_direct_llm_no_proxy() -> list[str]:
    return ensure_no_proxy(DIRECT_LLM_NO_PROXY_HOSTS)


def ensure_no_proxy(hosts: tuple[str, ...]) -> list[str]:
    existing_values: list[str] = []
    for key in ("NO_PROXY", "no_proxy"):
        existing_values.extend(_split_no_proxy(os.environ.get(key, "")))

    merged: list[str] = []
    seen: set[str] = set()
    for item in [*existing_values, *hosts]:
        normalized = item.strip()
        if not normalized:
            continue
        marker = normalized.lower()
        if marker in seen:
            continue
        merged.append(normalized)
        seen.add(marker)

    value = ",".join(merged)
    os.environ["NO_PROXY"] = value
    os.environ["no_proxy"] = value
    return merged


def _split_no_proxy(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _configured_direct_hosts() -> tuple[str, ...]:
    raw = os.environ.get("TRADING_AGENTS_DIRECT_HOSTS", "")
    return tuple(_split_no_proxy(raw))
