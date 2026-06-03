"""
Data sources subpackage.
Expose adapters and manager for backward-compatible imports.
"""
from .base import DataSourceAdapter
from .tushare import TushareAdapter
from .akshare import AKShareAdapter
from .baostock import BaoStockAdapter
from .manager import DataSourceManager
