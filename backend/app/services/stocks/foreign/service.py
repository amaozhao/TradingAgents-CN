from .base import ForeignStockBaseMixin
from .cache import ForeignStockCacheMixin
from .info import ForeignStockInfoMixin
from .kline import ForeignStockKlineMixin
from .news import ForeignStockNewsMixin
from .public import ForeignStockPublicMixin
from .quote import ForeignStockQuoteMixin


class ForeignStockService(
    ForeignStockBaseMixin,
    ForeignStockCacheMixin,
    ForeignStockPublicMixin,
    ForeignStockQuoteMixin,
    ForeignStockInfoMixin,
    ForeignStockKlineMixin,
    ForeignStockNewsMixin,
):
    """港股和美股数据服务（复用统一数据源管理器，按数据库优先级调用）"""
