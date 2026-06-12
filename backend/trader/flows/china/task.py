from .base import _OptimizedChinaDataProviderMixin2
from .common import _OptimizedChinaDataProviderMixin1
from .models import _OptimizedChinaDataProviderMixin3
from .query import _OptimizedChinaDataProviderMixin4
from .service import _OptimizedChinaDataProviderMixin5


class OptimizedChinaDataProvider(
    _OptimizedChinaDataProviderMixin1,
    _OptimizedChinaDataProviderMixin2,
    _OptimizedChinaDataProviderMixin3,
    _OptimizedChinaDataProviderMixin4,
    _OptimizedChinaDataProviderMixin5,
):
    """优化的A股数据提供器 - 集成缓存和Tushare数据接口"""
