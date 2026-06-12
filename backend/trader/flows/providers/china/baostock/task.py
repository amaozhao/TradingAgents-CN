from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import BaoStockProvider

def get_baostock_provider() -> BaoStockProvider:
    """获取全局BaoStock提供器实例"""
    global _baostock_provider
    if _baostock_provider is None:
        _baostock_provider = BaoStockProvider()
    return _baostock_provider
