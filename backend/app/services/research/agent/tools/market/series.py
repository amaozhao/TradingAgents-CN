from __future__ import annotations

import asyncio
import importlib
import math
import os
import socket
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd

from app.core.network.proxy import ensure_cn_market_no_proxy
from app.core.session import get_session_factory
from app.db.stock import get_market_quote, get_stock_basic_info, list_stock_daily_quotes


DEFAULT_HISTORY_DAYS = 252
OKX_BASE_URL = "https://www.okx.com/api/v5"
OKX_MAX_PER_PAGE = 300
OKX_INTERVAL = "1D"
OKX_TIMEOUT_SECONDS = float(os.getenv("OKX_TIMEOUT_S", "15"))
OKX_MAX_PAGES = int(os.getenv("OKX_MAX_PAGES", "20"))
CCXT_EXCHANGE = os.getenv("CCXT_EXCHANGE", "binance").strip().lower() or "binance"
CCXT_TIMEOUT_MS = int(os.getenv("CCXT_TIMEOUT_MS", "15000"))
CCXT_INTERVAL = "1d"
DEFAULT_EXTERNAL_PROXY_HOST = "127.0.0.1"
DEFAULT_EXTERNAL_PROXY_PORT = 7897


def normalize_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if text.endswith(".US"):
        text = text[:-3]
    if text.endswith((".SH", ".SZ", ".BJ")):
        return text[:6]
    if text.startswith(("SH", "SZ", "BJ")) and text[2:].isdigit():
        return text[2:].zfill(6)
    if text.endswith("USDT") and "-" not in text and "/" not in text:
        return f"{text[:-4]}-USDT"
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def normalize_symbols(symbols: Iterable[Any] | Mapping[str, Any] | Any) -> list[str]:
    if isinstance(symbols, Mapping):
        for key in ("symbols", "items", "item", "codes", "value"):
            value = symbols.get(key)
            if value is not None:
                symbols = value
                break
    if isinstance(symbols, str):
        symbols = symbols.replace("，", ",").split(",")
    if not isinstance(symbols, Iterable) or isinstance(symbols, (bytes, bytearray)):
        symbols = [symbols]
    seen: set[str] = set()
    clean: list[str] = []
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if normalized and normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    return clean


def detect_market(symbol: str) -> str:
    text = normalize_symbol(symbol)
    if text.isdigit() and len(text) == 6:
        return "CN"
    if "USDT" in text or text.endswith("-USD") or text.endswith("/USD"):
        return "CRYPTO"
    if text.isalpha() and 1 <= len(text) <= 8:
        return "US"
    return "UNKNOWN"


def default_start_date(
    end_date: str | None = None, days: int = DEFAULT_HISTORY_DAYS
) -> str:
    end = _date_from_text(end_date) or date.today()
    return (end - timedelta(days=days)).isoformat()


async def lookup_market_snapshot(
    symbol: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = DEFAULT_HISTORY_DAYS,
) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    market = detect_market(normalized)
    info = await _get_basic_info(normalized)
    quote = await _get_quote(normalized)
    series = await load_price_series(
        [normalized],
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    history = series.get(normalized, {})
    status = "completed" if info or quote or history.get("prices") else "degraded"
    snapshot = {
        "symbol": normalized,
        "market": market,
        "basic_info": info,
        "quote": quote,
        "history": history,
        "status": status,
    }
    if status == "degraded":
        snapshot["reason"] = history.get("reason") or _market_data_unavailable_reason(
            market, []
        )
        if history.get("source_diagnostics"):
            snapshot["source_diagnostics"] = history["source_diagnostics"]
    return snapshot


async def load_price_series(
    symbols: Iterable[Any],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = DEFAULT_HISTORY_DAYS,
) -> dict[str, dict[str, Any]]:
    clean_symbols = normalize_symbols(symbols)
    if not clean_symbols:
        return {}

    resolved_end = end_date or date.today().isoformat()
    resolved_start = start_date or default_start_date(resolved_end, max(limit, 30))
    results: dict[str, dict[str, Any]] = {}
    for symbol in clean_symbols:
        rows = await _load_from_postgres(
            symbol, start_date=resolved_start, end_date=resolved_end, limit=limit
        )
        source = "postgres"
        provider_diagnostics: list[dict[str, Any]] = []
        if not rows:
            rows, source, provider_diagnostics = await _load_from_provider(
                symbol, start_date=resolved_start, end_date=resolved_end
            )

        prices = _rows_to_prices(rows)
        returns = _returns_from_prices(prices)
        status = "completed" if len(prices) >= 2 else "degraded"
        results[symbol] = {
            "symbol": symbol,
            "market": detect_market(symbol),
            "source": source if prices else None,
            "start_date": resolved_start,
            "end_date": resolved_end,
            "observations": len(prices),
            "prices": prices,
            "returns": returns,
            "last": prices[-1] if prices else None,
            "status": status,
            "reason": None
            if status == "completed"
            else _market_data_unavailable_reason(
                detect_market(symbol), provider_diagnostics
            ),
            "source_diagnostics": provider_diagnostics,
        }
    return results


def _market_data_unavailable_reason(
    market: str,
    diagnostics: list[dict[str, Any]],
) -> str:
    if market == "CN":
        failed_sources = [
            str(item.get("source"))
            for item in diagnostics
            if item.get("source")
            and item.get("status") in {"empty", "error", "timeout"}
        ]
        source_text = (
            "、".join(failed_sources)
            if failed_sources
            else "本地缓存、AKShare、BaoStock"
        )
        return (
            f"A 股行情数据未取得可用价格序列：{source_text} 没有返回足够数据。"
            "请确认国内行情接口直连可用；如需估值/财务字段，再配置有效 TUSHARE_TOKEN。"
        )
    if market in {"US", "CRYPTO"}:
        return "外部行情数据源未返回足够价格序列，请检查网络代理或 yfinance 可用性。"
    return "未识别的标的类型，无法从当前免费数据源获取价格序列。"


def _provider_diagnostic(
    source: str, status: str, message: str, **extra: Any
) -> dict[str, Any]:
    diagnostic = {"source": source, "status": status, "message": message}
    diagnostic.update({key: value for key, value in extra.items() if value is not None})
    return diagnostic


def build_returns_frame(series_map: dict[str, dict[str, Any]]) -> pd.DataFrame:
    columns: dict[str, pd.Series] = {}
    for symbol, data in series_map.items():
        prices = data.get("prices") if isinstance(data, dict) else None
        if not isinstance(prices, list) or len(prices) < 2:
            continue
        frame = pd.DataFrame(prices)
        if not {"date", "close"}.issubset(frame.columns):
            continue
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame.dropna(subset=["date", "close"]).sort_values("date")
        returns = frame.set_index("date")["close"].pct_change().dropna()
        if not returns.empty:
            columns[symbol] = returns
    if not columns:
        return pd.DataFrame()
    return pd.DataFrame(columns).dropna(how="all")


def summarize_returns(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {"observations": 0}
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / len(clean)
    volatility = math.sqrt(variance)
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in clean:
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    annual_factor = 252
    annual_return = equity ** (annual_factor / len(clean)) - 1 if equity > 0 else -1.0
    annual_volatility = volatility * math.sqrt(annual_factor)
    return {
        "observations": len(clean),
        "total_return": round(equity - 1.0, 6),
        "annual_return": round(annual_return, 6),
        "mean_return": round(mean, 8),
        "volatility": round(volatility, 8),
        "annual_volatility": round(annual_volatility, 6),
        "sharpe": round((mean / volatility) * math.sqrt(annual_factor), 6)
        if volatility > 0
        else None,
        "max_drawdown": round(max_drawdown, 6),
        "win_rate": round(len([value for value in clean if value > 0]) / len(clean), 6),
    }


async def _get_basic_info(symbol: str) -> dict[str, Any] | None:
    try:
        async with get_session_factory()() as session:
            return await get_stock_basic_info(session, symbol)
    except Exception:
        return None


async def _get_quote(symbol: str) -> dict[str, Any] | None:
    try:
        async with get_session_factory()() as session:
            return await get_market_quote(session, symbol)
    except Exception:
        return None


async def _load_from_postgres(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    try:
        async with get_session_factory()() as session:
            rows = await list_stock_daily_quotes(
                session,
                market=detect_market(symbol)
                if detect_market(symbol) != "UNKNOWN"
                else None,
                code=symbol,
                start_date=start_date,
                end_date=end_date,
                period="daily",
                limit=max(limit, DEFAULT_HISTORY_DAYS),
            )
    except Exception:
        return []
    return list(reversed(rows))


async def _load_from_provider(
    symbol: str,
    *,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, Any]]]:
    market = detect_market(symbol)
    diagnostics: list[dict[str, Any]] = []
    if market == "CN":
        ensure_cn_market_no_proxy()
        for source, fetcher in (
            ("akshare", _fetch_cn_akshare),
            ("baostock", _fetch_cn_baostock),
        ):
            rows, diagnostic = await _bounded_provider(
                source,
                fetcher(symbol, start_date, end_date),
                timeout=8,
            )
            diagnostics.append(diagnostic)
            if rows:
                return rows, source, diagnostics
        return [], None, diagnostics
    if market == "CRYPTO":
        for source, fetcher in (
            ("okx", _fetch_okx),
            ("ccxt", _fetch_ccxt),
            ("yfinance", _fetch_yfinance),
        ):
            rows, diagnostic = await _bounded_provider(
                source,
                fetcher(symbol, start_date, end_date),
                timeout=15,
            )
            diagnostics.append(diagnostic)
            if rows:
                return rows, source, diagnostics
        return [], None, diagnostics
    if market == "US":
        rows, diagnostic = await _bounded_provider(
            "yfinance",
            _fetch_yfinance(symbol, start_date, end_date),
            timeout=8,
        )
        diagnostics.append(diagnostic)
        return (rows, "yfinance", diagnostics) if rows else ([], None, diagnostics)
    return [], None, diagnostics


async def _bounded_provider(
    source: str,
    coro,
    *,
    timeout: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        rows = await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError:
        return [], _provider_diagnostic(
            source,
            "timeout",
            f"{source} request exceeded {timeout:.0f}s timeout.",
            timeout_seconds=timeout,
        )
    except Exception as exc:
        return [], _provider_diagnostic(
            source, "error", str(exc), error_type=type(exc).__name__
        )
    if rows:
        return rows, _provider_diagnostic(
            source, "ok", f"{source} returned {len(rows)} rows.", rows=len(rows)
        )
    return [], _provider_diagnostic(
        source, "empty", f"{source} returned no usable rows."
    )


async def _fetch_cn_akshare(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    try:
        get_provider = getattr(
            importlib.import_module("trader.flows.providers.china.akshare"),
            "get_akshare_provider",
        )
        provider = get_provider()
        frame = await provider.get_historical_data(symbol, start_date, end_date)
        return _frame_to_rows(frame, symbol=symbol, source="akshare")
    except Exception:
        return []


async def _fetch_cn_baostock(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    try:
        get_provider = getattr(
            importlib.import_module("trader.flows.providers.china.baostock"),
            "get_baostock_provider",
        )
        provider = get_provider()
        frame = await provider.get_historical_data(symbol, start_date, end_date)
        return _frame_to_rows(frame, symbol=symbol, source="baostock")
    except Exception:
        return []


async def _fetch_yfinance(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    def fetch() -> pd.DataFrame:
        yf = importlib.import_module("yfinance")
        ticker = _to_yfinance_symbol(symbol)
        return yf.download(
            ticker, start=start_date, end=end_date, progress=False, auto_adjust=False
        )

    try:
        frame = await asyncio.to_thread(fetch)
        return _frame_to_rows(frame, symbol=symbol, source="yfinance")
    except Exception:
        return []


async def _fetch_okx(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    inst_id = _to_okx_symbol(symbol)
    start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)
    rows: list[list[str]] = []
    after = str(end_ts)

    async with httpx.AsyncClient(
        timeout=OKX_TIMEOUT_SECONDS,
        proxy=_external_proxy_url(),
    ) as client:
        for _ in range(max(1, OKX_MAX_PAGES)):
            response = await client.get(
                f"{OKX_BASE_URL}/market/candles",
                params={
                    "instId": inst_id,
                    "bar": OKX_INTERVAL,
                    "limit": str(OKX_MAX_PER_PAGE),
                    "after": after,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != "0":
                message = str(payload.get("msg") or "OKX request failed")
                raise ValueError(message)
            page_rows = [
                item
                for item in payload.get("data") or []
                if isinstance(item, list) and len(item) >= 9 and item[8] == "1"
            ]
            if not page_rows:
                break
            rows.extend(page_rows)
            oldest_ts = int(page_rows[-1][0])
            if oldest_ts <= start_ts or len(page_rows) < OKX_MAX_PER_PAGE:
                break
            after = str(oldest_ts)

    if not rows:
        return []
    frame = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volume_currency",
            "volume_quote",
            "confirm",
        ],
    )
    frame["trade_date"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms")
    frame = frame[
        (frame["trade_date"] >= pd.Timestamp(start_ts, unit="ms"))
        & (frame["trade_date"] < pd.Timestamp(end_ts, unit="ms"))
    ]
    return _frame_to_rows(
        frame[["trade_date", "open", "high", "low", "close", "volume"]],
        symbol=symbol,
        source="okx",
    )


async def _fetch_ccxt(
    symbol: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    try:
        ccxt = importlib.import_module("ccxt")
    except ImportError:
        return []

    def fetch() -> pd.DataFrame:
        exchange_cls = getattr(ccxt, CCXT_EXCHANGE, None) or getattr(ccxt, "binance")
        exchange = exchange_cls(
            {
                "enableRateLimit": True,
                "timeout": CCXT_TIMEOUT_MS,
                **_ccxt_proxy_config(),
            }
        )
        ccxt_symbol = _to_ccxt_symbol(symbol)
        since_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ms = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)
        cursor = since_ms
        all_rows: list[list[Any]] = []
        for _ in range(200):
            page_rows = exchange.fetch_ohlcv(
                ccxt_symbol,
                CCXT_INTERVAL,
                since=cursor,
                limit=1000,
            )
            if not page_rows:
                break
            all_rows.extend(page_rows)
            last_ts = int(page_rows[-1][0])
            if last_ts >= end_ms or len(page_rows) < 1000:
                break
            cursor = last_ts + 1
        if not all_rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            all_rows,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["trade_date"] = pd.to_datetime(frame["timestamp"], unit="ms")
        start = pd.Timestamp(since_ms, unit="ms")
        end = pd.Timestamp(end_ms, unit="ms")
        return frame[(frame["trade_date"] >= start) & (frame["trade_date"] < end)]

    frame = await asyncio.to_thread(fetch)
    return _frame_to_rows(
        frame[["trade_date", "open", "high", "low", "close", "volume"]]
        if not frame.empty
        else frame,
        symbol=symbol,
        source="ccxt",
    )


def _to_yfinance_symbol(symbol: str) -> str:
    text = normalize_symbol(symbol)
    if text.endswith("-USDT"):
        return text.replace("-USDT", "-USD")
    if text.endswith("/USDT"):
        return text.replace("/USDT", "-USD")
    return text


def _to_okx_symbol(symbol: str) -> str:
    text = normalize_symbol(symbol).replace("/", "-")
    if text.endswith("-USD"):
        return text[:-4] + "-USDT"
    return text


def _to_ccxt_symbol(symbol: str) -> str:
    text = normalize_symbol(symbol).replace("-", "/")
    if text.endswith("/USD"):
        return text[:-4] + "/USDT"
    return text


def _ccxt_proxy_config() -> dict[str, str]:
    proxy = _external_proxy_url()
    return {"proxies": {"http": proxy, "https": proxy}} if proxy else {}


def _external_proxy_url() -> str | None:
    for key in (
        "TRADING_AGENTS_PROXY_URL",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        value = os.getenv(key, "").strip()
        if value:
            return value

    host = (
        os.getenv("TRADING_AGENTS_PROXY_HOST")
        or os.getenv("CLASH_PROXY_HOST")
        or DEFAULT_EXTERNAL_PROXY_HOST
    )
    raw_port = (
        os.getenv("TRADING_AGENTS_PROXY_PORT")
        or os.getenv("CLASH_MIXED_PORT")
        or str(DEFAULT_EXTERNAL_PROXY_PORT)
    )
    try:
        port = int(raw_port)
    except ValueError:
        return None
    if _tcp_port_open(host, port):
        return f"http://{host}:{port}"
    return None


def _tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _frame_to_rows(frame: Any, *, symbol: str, source: str) -> list[dict[str, Any]]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(column[0]).lower() for column in df.columns]
    else:
        df.columns = [str(column).lower() for column in df.columns]
    if "date" not in df.columns and "trade_date" not in df.columns:
        df = df.reset_index()
        df.columns = [str(column).lower() for column in df.columns]
    date_column = (
        "date"
        if "date" in df.columns
        else "trade_date"
        if "trade_date" in df.columns
        else df.columns[0]
    )
    close_column = _first_existing(df, ("close", "收盘", "收盘价"))
    if not close_column:
        return []
    open_column = _first_existing(df, ("open", "开盘", "开盘价"))
    high_column = _first_existing(df, ("high", "最高", "最高价"))
    low_column = _first_existing(df, ("low", "最低", "最低价"))
    volume_column = _first_existing(df, ("volume", "vol", "成交量"))
    rows: list[dict[str, Any]] = []
    for item in df.to_dict(orient="records"):
        close = _number(item.get(close_column))
        trade_date = _date_text(item.get(date_column))
        if close is None or not trade_date:
            continue
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "open": _number(item.get(open_column)) if open_column else None,
                "high": _number(item.get(high_column)) if high_column else None,
                "low": _number(item.get(low_column)) if low_column else None,
                "close": close,
                "volume": _number(item.get(volume_column)) if volume_column else None,
                "data_source": source,
            }
        )
    return rows


def _rows_to_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prices: list[dict[str, Any]] = []
    for row in rows:
        close = _number(row.get("close"))
        trade_date = _date_text(row.get("trade_date") or row.get("date"))
        if close is None or not trade_date:
            continue
        prices.append(
            {
                "date": trade_date,
                "close": close,
                "open": _number(row.get("open")),
                "high": _number(row.get("high")),
                "low": _number(row.get("low")),
                "volume": _number(row.get("volume") or row.get("vol")),
            }
        )
    return sorted(prices, key=lambda item: item["date"])


def _returns_from_prices(prices: list[dict[str, Any]]) -> list[float]:
    returns: list[float] = []
    previous: float | None = None
    for item in prices:
        close = _number(item.get("close"))
        if close is None:
            continue
        if previous and previous != 0:
            returns.append((close / previous) - 1.0)
        previous = close
    return returns


def _first_existing(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lowered = {str(column).lower(): str(column) for column in frame.columns}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "date") and not isinstance(value, date):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _date_from_text(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(_date_text(value) or "")
    except ValueError:
        return None
