"""Symbol normalization and no-data error helpers."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class NoMarketDataError(Exception):
    """Raised when a market-data vendor has no rows for a requested symbol."""

    def __init__(self, symbol: str, canonical: str | None = None, detail: str = ""):
        self.symbol = symbol
        self.canonical = canonical or symbol
        self.detail = detail
        msg = f"No market data for {symbol!r}"
        if canonical and canonical != symbol:
            msg += f" (queried as {canonical!r})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


_FOREX_CURRENCIES = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
        "CNY", "CNH", "HKD", "SGD", "SEK", "NOK", "DKK", "PLN",
        "MXN", "ZAR", "TRY", "INR", "KRW", "BRL", "RUB", "THB",
    }
)

_CRYPTO_BASES = frozenset(
    {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH", "DOT", "AVAX", "LINK"}
)

_ALIASES = {
    "XAUUSD": "GC=F", "XAU": "GC=F", "GOLD": "GC=F",
    "XAGUSD": "SI=F", "XAG": "SI=F", "SILVER": "SI=F",
    "XPTUSD": "PL=F", "XPDUSD": "PA=F",
    "WTICOUSD": "CL=F", "USOIL": "CL=F", "WTI": "CL=F",
    "BCOUSD": "BZ=F", "UKOIL": "BZ=F", "BRENT": "BZ=F",
    "NATGAS": "NG=F", "XNGUSD": "NG=F",
    "COPPER": "HG=F", "XCUUSD": "HG=F",
    "SPX500": "^GSPC", "US500": "^GSPC", "SPX": "^GSPC",
    "NAS100": "^NDX", "US100": "^NDX", "USTEC": "^NDX",
    "US30": "^DJI", "DJI30": "^DJI", "WS30": "^DJI",
    "GER40": "^GDAXI", "GER30": "^GDAXI", "DE40": "^GDAXI",
    "UK100": "^FTSE", "JP225": "^N225", "JPN225": "^N225",
    "FRA40": "^FCHI", "EU50": "^STOXX50E", "HK50": "^HSI",
}

_YAHOO_SAFE = re.compile(r"^[A-Za-z0-9._\-\^=]+$")
_CN_STOCK = re.compile(r"^(?:[036]\d{5}|[036]\d{5}\.(?:SH|SZ|SS))$")


def normalize_symbol(raw: str) -> str:
    """Map common broker symbols to vendor-safe canonical symbols.

    CN A-share symbols are preserved because CN provider routing owns their
    exchange semantics. US/crypto/forex aliases follow the upstream behavior.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw

    s = raw.strip().upper()
    s = s.rstrip("+")

    if _CN_STOCK.fullmatch(s):
        canonical = s
    elif s in _ALIASES:
        canonical = _ALIASES[s]
    elif len(s) == 6 and s[:3] in _CRYPTO_BASES and s[3:] == "USD":
        canonical = f"{s[:3]}-USD"
    elif s[:-3] in _CRYPTO_BASES and s.endswith("USD") and "-" not in s:
        canonical = f"{s[:-3]}-USD"
    elif len(s) == 6 and s[:3] in _FOREX_CURRENCIES and s[3:] in _FOREX_CURRENCIES:
        canonical = f"{s}=X"
    else:
        canonical = s

    if canonical != raw.strip().upper():
        logger.info("Resolved symbol %r to canonical symbol %r", raw, canonical)
    return canonical


def is_yahoo_safe(symbol: str) -> bool:
    return bool(symbol) and _YAHOO_SAFE.fullmatch(symbol) is not None
