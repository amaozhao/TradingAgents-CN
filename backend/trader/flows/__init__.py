from __future__ import annotations

import importlib
from typing import Any


_INTERFACE_EXPORTS = {
    "get_china_stock_data_tushare",
    "get_china_stock_data_unified",
    "get_china_stock_fundamentals_tushare",
    "get_china_stock_info_unified",
    "get_current_china_data_source",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_finnhub_news",
    "get_google_news",
    "get_hk_stock_data_unified",
    "get_hk_stock_info_unified",
    "get_reddit_company_news",
    "get_reddit_global_news",
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_statements",
    "get_stock_data_by_market",
    "get_stock_stats_indicators_window",
    "get_stockstats_indicator",
    "get_yfin_data",
    "get_yfin_data_window",
    "switch_china_data_source",
}

_OTHER_EXPORTS = {
    "get_data_in_range": (".providers.us", ".finnhub"),
    "fetch_top_from_category": (".news", ".news.reddit"),
    "get_news_data": (".news", ".news.google"),
    "YFinanceUtils": (".providers.us", ".providers.us.yfinance"),
    "YFINANCE_AVAILABLE": (".providers.us",),
    "StockstatsUtils": (".technical", ".technical.stats"),
    "STOCKSTATS_AVAILABLE": (".technical",),
}


def __getattr__(name: str) -> Any:
    if name in _INTERFACE_EXPORTS:
        module = importlib.import_module(".interface", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value

    if name in _OTHER_EXPORTS:
        for module_path in _OTHER_EXPORTS[name]:
            try:
                module = importlib.import_module(module_path, __name__)
                value = getattr(module, name)
            except (ImportError, AttributeError):
                continue
            globals()[name] = value
            return value
        return False if name.endswith("_AVAILABLE") else None

    raise AttributeError(name)


__all__ = [
    "get_finnhub_news",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_google_news",
    "get_reddit_global_news",
    "get_reddit_company_news",
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_statements",
    "get_stock_stats_indicators_window",
    "get_stockstats_indicator",
    "get_yfin_data_window",
    "get_yfin_data",
    "get_china_stock_data_tushare",
    "get_china_stock_fundamentals_tushare",
    "get_china_stock_data_unified",
    "get_china_stock_info_unified",
    "switch_china_data_source",
    "get_current_china_data_source",
    "get_hk_stock_data_unified",
    "get_hk_stock_info_unified",
    "get_stock_data_by_market",
]
