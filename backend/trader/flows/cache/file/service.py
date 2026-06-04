from .base import StockDataCacheBaseMixin
from .fundamentals import StockDataCacheFundamentalsMixin
from .maintenance import StockDataCacheMaintenanceMixin
from .news import StockDataCacheNewsMixin
from .policy import StockDataCachePolicyMixin
from .stock import StockDataCacheStockMixin


class StockDataCache(
    StockDataCacheBaseMixin,
    StockDataCachePolicyMixin,
    StockDataCacheStockMixin,
    StockDataCacheNewsMixin,
    StockDataCacheFundamentalsMixin,
    StockDataCacheMaintenanceMixin,
):
    """股票数据缓存管理器 - 支持美股和A股数据缓存优化"""
