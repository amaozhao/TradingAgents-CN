from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import _StockDataPreparerMixin2
    from .common import _StockDataPreparerMixin1


class StockDataPreparer(_StockDataPreparerMixin1, _StockDataPreparerMixin2):
    """股票数据预获取和验证器"""
