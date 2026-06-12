from .common import (
    Any,
    HKStockProvider,
    asyncio,
    defaultdict,
    get_cache,
    logger,
)


class ForeignStockBaseMixin:
    # 缓存时间配置（秒）
    CACHE_TTL = {
        "HK": {
            "quote": 600,  # 10分钟（实时行情）
            "info": 86400,  # 1天（基础信息）
            "kline": 7200,  # 2小时（K线数据）
        },
        "US": {
            "quote": 600,  # 10分钟
            "info": 86400,  # 1天
            "kline": 7200,  # 2小时
        },
    }

    def __init__(self, db=None, cache=None, hk_provider=None):
        # 使用统一缓存系统（自动选择 PostgreSQL/Redis/File）
        self.cache = cache if cache is not None else get_cache()

        # 初始化港股数据源提供者
        self.hk_provider = hk_provider if hk_provider is not None else HKStockProvider()

        # 保存数据库连接（用于查询数据源优先级）
        self.db: Any = db

        # 🔥 请求去重：为每个 (market, code, data_type) 创建独立的锁
        self._request_locks = defaultdict(asyncio.Lock)

        # 🔥 正在进行的请求缓存（用于共享结果）
        self._pending_requests = {}

        logger.info("✅ ForeignStockService 初始化完成（已启用请求去重）")
