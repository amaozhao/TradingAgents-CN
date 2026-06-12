from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _BaoStockProviderMixin2
    from .common import _BaoStockProviderMixin1
    from .imports import BaseStockDataProvider

class BaoStockProvider(_BaoStockProviderMixin1, _BaoStockProviderMixin2, BaseStockDataProvider):
    """BaoStock统一数据提供器"""
