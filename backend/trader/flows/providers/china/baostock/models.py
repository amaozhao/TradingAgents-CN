# ruff: noqa: F401,F403,F405,F821
class BaoStockProvider(
    _BaoStockProviderMixin1, _BaoStockProviderMixin2, BaseStockDataProvider
):
    """BaoStock统一数据提供器"""
