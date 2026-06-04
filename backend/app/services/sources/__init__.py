"""
Data sources subpackage.
Expose adapters and manager for backward-compatible imports.
"""

from .akshare import AKShareAdapter
from .baostock import BaoStockAdapter
from .base import DataSourceAdapter
from .manager import DataSourceManager
from .tushare import TushareAdapter

__all__ = [
    "AKShareAdapter",
    "BaoStockAdapter",
    "DataSourceAdapter",
    "DataSourceManager",
    "TushareAdapter",
]
