"""
缓存管理模块

支持多种缓存策略：
- 文件缓存（默认）- 简单稳定，不依赖外部服务
- 数据库缓存（可选）- PostgreSQL + Redis，性能更好
- 自适应缓存（推荐）- 自动选择最佳后端

使用方法：
    from trader.flows.cache import get_cache
    cache = get_cache()  # 自动选择最佳缓存策略

配置缓存策略：
    export TA_CACHE_STRATEGY=integrated  # 启用集成缓存（PostgreSQL/Redis）
    export TA_CACHE_STRATEGY=file        # 使用文件缓存（默认）
"""

import importlib
from typing import Any

from app.core.config import settings

# 导入日志模块
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")


def _optional_attr(module_name: str, attr_name: str) -> Any:
    try:
        return getattr(importlib.import_module(module_name), attr_name)
    except (AttributeError, ImportError):
        return None


# 导入文件缓存
StockDataCache = _optional_attr("trader.flows.cache.file", "StockDataCache")
FILE_CACHE_AVAILABLE = StockDataCache is not None

# 导入数据库缓存
DatabaseCacheManager = _optional_attr(
    "trader.flows.cache.database", "DatabaseCacheManager"
)
DB_CACHE_AVAILABLE = DatabaseCacheManager is not None

# 导入自适应缓存
AdaptiveCacheSystem = _optional_attr(
    "trader.flows.cache.adaptive", "AdaptiveCacheSystem"
)
ADAPTIVE_CACHE_AVAILABLE = AdaptiveCacheSystem is not None

# 导入集成缓存
IntegratedCacheManager = _optional_attr(
    "trader.flows.cache.integrated", "IntegratedCacheManager"
)
INTEGRATED_CACHE_AVAILABLE = IntegratedCacheManager is not None

# 导入应用缓存适配器（函数，非类）
get_basics_from_cache = _optional_attr(
    "trader.flows.cache.app", "get_basics_from_cache"
)
get_market_quote_dataframe = _optional_attr(
    "trader.flows.cache.app", "get_market_quote_dataframe"
)
APP_CACHE_AVAILABLE = (
    get_basics_from_cache is not None and get_market_quote_dataframe is not None
)

# 导入 PostgreSQL 缓存适配器
PostgresCacheAdapter = _optional_attr(
    "trader.flows.cache.postgres", "PostgresCacheAdapter"
)
POSTGRES_CACHE_ADAPTER_AVAILABLE = PostgresCacheAdapter is not None

# 全局缓存实例
_cache_instance = None

# 默认缓存策略（改为 integrated，优先使用 PostgreSQL/Redis 缓存）
DEFAULT_CACHE_STRATEGY = settings.TA_CACHE_STRATEGY


def get_cache() -> Any:
    """
    获取缓存实例（统一入口）

    根据环境变量 TA_CACHE_STRATEGY 选择缓存策略：
    - "file" (默认): 使用文件缓存
    - "integrated": 使用集成缓存（自动选择 PostgreSQL/Redis/File）
    - "adaptive": 使用自适应缓存（同 integrated）

    环境变量设置：
        export TA_CACHE_STRATEGY=integrated  # Linux/Mac
        set TA_CACHE_STRATEGY=integrated     # Windows

    返回：
        StockDataCache 或 IntegratedCacheManager 实例
    """
    global _cache_instance

    if _cache_instance is None:
        if DEFAULT_CACHE_STRATEGY in ["integrated", "adaptive"]:
            if INTEGRATED_CACHE_AVAILABLE:
                try:
                    cache_cls: Any = IntegratedCacheManager
                    _cache_instance = cache_cls()
                    logger.info(
                        "✅ 使用集成缓存系统（支持 PostgreSQL/Redis/File 自动选择）"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ 集成缓存初始化失败，降级到文件缓存: {e}")
                    file_cache_cls: Any = StockDataCache
                    _cache_instance = file_cache_cls()
            else:
                logger.warning("⚠️ 集成缓存不可用，使用文件缓存")
                file_cache_cls: Any = StockDataCache
                _cache_instance = file_cache_cls()
        else:
            file_cache_cls: Any = StockDataCache
            _cache_instance = file_cache_cls()
            logger.info("✅ 使用文件缓存系统")

    return _cache_instance


def close_cache() -> None:
    """关闭并清空全局缓存实例。"""
    global _cache_instance

    if _cache_instance is not None:
        close = getattr(_cache_instance, "close", None)
        if close is not None:
            close()
        _cache_instance = None

    if DB_CACHE_AVAILABLE:
        close_database_manager = getattr(
            importlib.import_module("trader.config.databases"),
            "close_database_manager",
        )
        close_database_manager()


__all__ = [
    # 统一入口（推荐使用）
    "close_cache",
    "get_cache",
    # 缓存类（供高级用户直接使用）
    "StockDataCache",
    "IntegratedCacheManager",
    "DatabaseCacheManager",
    "AdaptiveCacheSystem",
    # 可用性标志
    "FILE_CACHE_AVAILABLE",
    "DB_CACHE_AVAILABLE",
    "ADAPTIVE_CACHE_AVAILABLE",
    "INTEGRATED_CACHE_AVAILABLE",
    # 应用缓存适配器
    "get_basics_from_cache",
    "get_market_quote_dataframe",
    "APP_CACHE_AVAILABLE",
    # PostgreSQL 缓存适配器
    "PostgresCacheAdapter",
    "POSTGRES_CACHE_ADAPTER_AVAILABLE",
]
