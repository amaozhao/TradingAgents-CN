"""Async Eastmoney public market data client."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

EASTMONEY_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://quote.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}
EASTMONEY_STOCK_FIELDS = "f43,f44,f45,f46,f57,f58,f60,f116,f117,f152,f162,f167,f170"
EASTMONEY_STOCK_ENDPOINTS = (
    "https://push2delay.eastmoney.com/api/qt/stock/get",
    "https://82.push2.eastmoney.com/api/qt/stock/get",
    "https://push2.eastmoney.com/api/qt/stock/get",
)


def eastmoney_secid(symbol: str) -> str:
    code = str(symbol).strip().zfill(6)
    market = "1" if code.startswith(("6", "9")) else "0"
    return f"{market}.{code}"


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", "-", "--"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _scaled(value: Any, precision: Any) -> float | None:
    number = _safe_float(value)
    digits = _safe_float(precision)
    if number is None:
        return None
    if digits is None:
        return number
    return number / (10 ** int(digits))


async def fetch_eastmoney_metrics(symbol: str) -> dict[str, Any]:
    code = str(symbol).strip().zfill(6)
    params = {"secid": eastmoney_secid(code), "fields": EASTMONEY_STOCK_FIELDS}

    async with httpx.AsyncClient(
        headers=EASTMONEY_HEADERS,
        timeout=12,
        trust_env=True,
        http2=False,
    ) as client:
        last_error: Exception | None = None
        for endpoint in EASTMONEY_STOCK_ENDPOINTS:
            try:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json().get("data") or {}
                if not data:
                    continue
                precision = data.get("f152")
                pe = _scaled(data.get("f162"), precision)
                pb = _scaled(data.get("f167"), precision)
                price = _scaled(data.get("f43"), precision)
                market_cap_raw = _safe_float(data.get("f116"))
                market_cap = (
                    market_cap_raw / 100000000 if market_cap_raw is not None else None
                )
                return {
                    "pe": pe,
                    "pb": pb,
                    "pe_ttm": pe,
                    "pb_mrq": pb,
                    "price": price,
                    "market_cap": market_cap,
                    "pct_chg": _scaled(data.get("f170"), precision),
                    "source": "eastmoney_public_snapshot",
                    "is_realtime": False,
                    "updated_at": datetime.now().isoformat(),
                    "note": "使用东方财富免费公开单股快照",
                }
            except Exception as exc:
                last_error = exc

    if last_error is not None:
        raise last_error
    return {}
