from .finnhub import get_finnhub_company_insider_transactions
from .finnhub import (
    get_simfin_balance_sheet,
    get_simfin_cashflow,
)
from .fundamentals import get_fundamentals_openai
from .hk import get_stock_data_by_market
from .imports import datetime, importlib
from .market import get_global_news_openai, get_stockstats_indicator
from .setup import AlphaVantageRateLimitError, NoMarketDataError, VENDOR_METHODS
from .social import get_google_news, get_simfin_income_statements


def _configured_vendor(category: str, method: str | None = None) -> str:
    try:
        get_runtime_config = getattr(
            importlib.import_module("trader.flows.config"), "get_config"
        )

        cfg = get_runtime_config()
    except Exception:
        cfg = {}

    if method:
        tool_vendors = cfg.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]
    return cfg.get("data_vendors", {}).get(category, "cn_unified")


def _category_for_method(method: str) -> str:
    if method in {"get_stock_data"}:
        return "core_stock_apis"
    if method in {"get_indicators"}:
        return "technical_indicators"
    if method in {
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
    }:
        return "fundamental_data"
    if method in {"get_news", "get_global_news", "get_insider_transactions"}:
        return "news_data"
    raise ValueError(f"Method '{method}' not found in any data category")


def _route_cn_unified(method: str, *args, **kwargs):
    if method == "get_stock_data":
        return get_stock_data_by_market(*args, **kwargs)
    if method == "get_indicators":
        symbol, indicator, curr_date = args[:3]
        look_back_days = args[3] if len(args) > 3 else kwargs.get("look_back_days", 30)
        return get_stockstats_indicator(symbol, indicator, curr_date, online=True)
    if method == "get_fundamentals":
        return get_fundamentals_openai(*args, **kwargs)
    if method == "get_balance_sheet":
        return get_simfin_balance_sheet(*args, **kwargs)
    if method == "get_cashflow":
        return get_simfin_cashflow(*args, **kwargs)
    if method == "get_income_statement":
        return get_simfin_income_statements(*args, **kwargs)
    if method == "get_news":
        ticker, start_date, end_date = args[:3]
        return get_google_news(ticker, start_date, end_date)
    if method == "get_global_news":
        curr_date = args[0]
        look_back_days = args[1] if len(args) > 1 and args[1] is not None else 7
        limit = args[2] if len(args) > 2 and args[2] is not None else 10
        return get_global_news_openai(curr_date, look_back_days, limit)
    if method == "get_insider_transactions":
        return get_finnhub_company_insider_transactions(
            args[0], datetime.now().strftime("%Y-%m-%d"), 15
        )
    raise ValueError(f"Method '{method}' not supported by cn_unified router")


def _route_upstream_vendor(vendor: str, method: str, *args, **kwargs):
    vendor_impl = VENDOR_METHODS.get(method, {}).get(vendor)
    if vendor_impl is not None:
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl
        return impl_func(*args, **kwargs)

    if method == "get_stock_data":
        if vendor == "alpha_vantage":
            get_stock = getattr(
                importlib.import_module("trader.flows.alpha.api"), "get_stock"
            )

            return get_stock(*args, **kwargs)
        get_yfin_data_online = getattr(
            importlib.import_module("trader.flows.yfinance.legacy"),
            "get_yfin_data_online",
        )

        return get_yfin_data_online(*args, **kwargs)
    if method == "get_indicators":
        if vendor == "alpha_vantage":
            get_indicator = getattr(
                importlib.import_module("trader.flows.alpha.api"), "get_indicator"
            )

            return get_indicator(*args, **kwargs)
        get_stock_stats_indicators_window = getattr(
            importlib.import_module("trader.flows.yfinance.legacy"),
            "get_stock_stats_indicators_window",
        )

        return get_stock_stats_indicators_window(*args, **kwargs)
    if method == "get_fundamentals":
        if vendor == "alpha_vantage":
            get_fundamentals = getattr(
                importlib.import_module("trader.flows.alpha.api"), "get_fundamentals"
            )
        else:
            get_fundamentals = getattr(
                importlib.import_module("trader.flows.yfinance.legacy"),
                "get_fundamentals",
            )

        return get_fundamentals(*args, **kwargs)
    if method == "get_news":
        if vendor == "alpha_vantage":
            get_news = getattr(
                importlib.import_module("trader.flows.alpha.api"), "get_news"
            )
        else:
            get_news = getattr(
                importlib.import_module("trader.flows.yfinance.news"),
                "get_news_yfinance",
            )

        return get_news(*args, **kwargs)
    if method == "get_global_news":
        if vendor == "alpha_vantage":
            get_global_news = getattr(
                importlib.import_module("trader.flows.alpha.api"), "get_global_news"
            )
        else:
            get_global_news = getattr(
                importlib.import_module("trader.flows.yfinance.news"),
                "get_global_news_yfinance",
            )

        return get_global_news(*args, **kwargs)
    if method == "get_insider_transactions":
        if vendor == "alpha_vantage":
            get_insider_transactions = getattr(
                importlib.import_module("trader.flows.alpha.api"),
                "get_insider_transactions",
            )
        else:
            get_insider_transactions = getattr(
                importlib.import_module("trader.flows.yfinance.legacy"),
                "get_insider_transactions",
            )

        return get_insider_transactions(*args, **kwargs)
    raise ValueError(f"Method '{method}' not supported by vendor '{vendor}'")


def _is_unusable_data_result(result) -> bool:
    if not isinstance(result, str):
        return False
    markers = (
        "NO_DATA_AVAILABLE",
        "数据获取失败",
        "所有美股数据源都不可用",
        "模拟数据（仅供演示）",
        "Do not estimate",
    )
    return any(marker in result for marker in markers)


def route_to_vendor(method: str, *args, **kwargs):
    """Route upstream-compatible tool calls without replacing CN data logic."""
    category = _category_for_method(method)
    vendor_config = _configured_vendor(category, method)
    vendors = [v.strip() for v in str(vendor_config).split(",") if v.strip()]
    if not vendors:
        vendors = ["cn_unified"]

    for vendor in VENDOR_METHODS.get(method, {}):
        if vendor not in vendors:
            vendors.append(vendor)

    first_error = None
    last_no_data = None
    for vendor in vendors:
        try:
            if vendor in {"cn_unified", "default"}:
                result = _route_cn_unified(method, *args, **kwargs)
            else:
                result = _route_upstream_vendor(vendor, method, *args, **kwargs)
            if _is_unusable_data_result(result):
                if first_error is None:
                    first_error = RuntimeError(
                        f"{vendor} returned unusable data for '{method}'"
                    )
                continue
            return result
        except AlphaVantageRateLimitError:
            continue
        except NoMarketDataError as exc:
            last_no_data = exc
            continue
        except Exception as exc:
            if first_error is None:
                first_error = exc
            continue

    if last_no_data is not None:
        symbol = getattr(last_no_data, "symbol", args[0] if args else "")
        canonical = getattr(last_no_data, "canonical", symbol)
        resolved = "" if canonical == symbol else f" (resolved to '{canonical}')"
        return (
            f"NO_DATA_AVAILABLE: No market data found for '{symbol}'{resolved} from "
            "any configured vendor. The symbol may be invalid, delisted, or not "
            "covered by configured data sources. Do not estimate or fabricate "
            "values; report that data is unavailable for this symbol."
        )

    if first_error is not None:
        return (
            f"NO_DATA_AVAILABLE: No usable data returned for method '{method}'. "
            f"First error: {type(first_error).__name__}: {first_error}. "
            "Do not estimate or fabricate values; report that data is unavailable."
        )
    raise RuntimeError(f"No available vendor for '{method}'")
