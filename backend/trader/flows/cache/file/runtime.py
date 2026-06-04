from .service import StockDataCache

# 全局缓存实例
_cache_instance = None


def get_cache() -> StockDataCache:
    """获取全局缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = StockDataCache()
    return _cache_instance
