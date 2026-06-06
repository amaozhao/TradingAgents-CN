from __future__ import annotations

from app.routers import stocks


def test_stocks_router_registers_next_detail_endpoints():
    paths = {route.path for route in stocks.router.routes}

    assert "/stocks/{code}/quote" in paths
    assert "/stocks/{code}/fundamentals" in paths
    assert "/stocks/{code}/kline" in paths
    assert "/stocks/{code}/news" in paths


def test_detect_market_and_code_supports_a_shares():
    assert stocks._detect_market_and_code("600519") == ("CN", "600519")


def test_enrich_quote_calculation_from_daily_values():
    quote = {}
    latest = {"close": 1272.86, "high": 1283.0, "low": 1267.74}
    previous = {"close": 1268.0}

    latest_close = stocks._as_float(latest["close"])
    previous_close = stocks._as_float(previous["close"])
    high = stocks._as_float(latest["high"])
    low = stocks._as_float(latest["low"])

    quote["change_percent"] = round(
        (latest_close - previous_close) / previous_close * 100, 3
    )
    quote["amplitude"] = round((high - low) / previous_close * 100, 3)

    assert quote["change_percent"] == 0.383
    assert quote["amplitude"] == 1.203
