from __future__ import annotations

import importlib


def test_file_cache_import_facade_exports_public_api() -> None:
    module = importlib.import_module("trader.flows.cache.file")

    assert hasattr(module, "StockDataCache")
    assert callable(module.get_cache)

    for method_name in (
        "save_stock_data",
        "load_stock_data",
        "find_cached_stock_data",
        "save_news_data",
        "save_fundamentals_data",
        "get_cache_stats",
    ):
        assert hasattr(module.StockDataCache, method_name)
