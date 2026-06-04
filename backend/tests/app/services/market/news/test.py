from __future__ import annotations

import importlib


def test_market_news_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.market.news")

    assert hasattr(module, "NewsQueryParams")
    assert hasattr(module, "NewsStats")
    assert hasattr(module, "NewsDataService")
    assert callable(module.get_news_data_service)

    service = module.NewsDataService()
    for method_name in (
        "save_news_data",
        "query_news",
        "get_latest_news",
        "get_news_statistics",
        "delete_old_news",
        "search_news",
    ):
        assert hasattr(service, method_name)
