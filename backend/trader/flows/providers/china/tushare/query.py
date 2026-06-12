from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _TushareProviderMixin2
    from .common import _TushareProviderMixin1
    from .imports import BaseStockDataProvider
    from .models import _TushareProviderMixin3

class TushareProvider(
    _TushareProviderMixin1,
    _TushareProviderMixin2,
    _TushareProviderMixin3,
    BaseStockDataProvider,
):
    """
    统一的Tushare数据提供器
    合并app层和trading_agents层的所有优势功能
    """
