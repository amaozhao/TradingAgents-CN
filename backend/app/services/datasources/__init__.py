"""
Data sources subpackage.
Expose adapters and manager for backward-compatible imports.
"""
from .datasourcebase import DataSourceAdapter
from .apptushareadapter import TushareAdapter
from .akshareadapter import AKShareAdapter
from .baostockadapter import BaoStockAdapter
from .manager import DataSourceManager

