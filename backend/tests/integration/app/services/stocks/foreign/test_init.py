from __future__ import annotations

import importlib


def test_foreign_stock_service_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.stocks.foreign")

    assert hasattr(module, "ForeignStockService")

    service = module.ForeignStockService(db=None, cache=object(), hk_provider=object())
    for method_name in (
        "get_quote",
        "get_basic_info",
        "get_kline",
        "get_hk_news",
        "get_us_news",
    ):
        assert hasattr(service, method_name)
