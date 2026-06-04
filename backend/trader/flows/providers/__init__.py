"""
统一数据源提供器包
按市场分类组织数据提供器
"""

from .base import BaseStockDataProvider

# 导入中国市场提供器（新路径）
try:
    from .china import (
        AKSHARE_AVAILABLE,
        BAOSTOCK_AVAILABLE,
        TUSHARE_AVAILABLE,
        AKShareProvider,
        BaoStockProvider,
        TushareProvider,
    )
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from .china.tushare import TushareProvider
    except ImportError:
        TushareProvider = None

    try:
        from .china.akshare import AKShareProvider
    except ImportError:
        AKShareProvider = None

    try:
        from .china.baostock import BaoStockProvider
    except ImportError:
        BaoStockProvider = None

    AKSHARE_AVAILABLE = AKShareProvider is not None
    TUSHARE_AVAILABLE = TushareProvider is not None
    BAOSTOCK_AVAILABLE = BaoStockProvider is not None

# 导入港股提供器
try:
    from .hk import (
        HK_PROVIDER_AVAILABLE,
        ImprovedHKStockProvider,
        get_improved_hk_provider,
    )
except ImportError:
    ImprovedHKStockProvider = None
    get_improved_hk_provider = None
    HK_PROVIDER_AVAILABLE = False

# 导入美股提供器
try:
    from .us import (
        FINNHUB_AVAILABLE,
        OPTIMIZED_US_AVAILABLE,
        YFINANCE_AVAILABLE,
        OptimizedUSDataProvider,
        YFinanceUtils,
        get_data_in_range,
    )
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from ..providers.us.yfinance import YFinanceUtils
    except ImportError:
        YFinanceUtils = None

    try:
        from .us.optimized import OptimizedUSDataProvider
    except ImportError:
        OptimizedUSDataProvider = None

    try:
        from ..finnhub import get_data_in_range
    except ImportError:
        get_data_in_range = None

    YFINANCE_AVAILABLE = YFinanceUtils is not None
    OPTIMIZED_US_AVAILABLE = OptimizedUSDataProvider is not None
    FINNHUB_AVAILABLE = get_data_in_range is not None

# 其他提供器（预留）
YahooProvider = None
FinnhubProvider = None

# TDXProvider 已移除
# try:
#     from .tdx_provider import TDXProvider
# except ImportError:
#     TDXProvider = None

__all__ = [
    # 基类
    "BaseStockDataProvider",
    # 中国市场
    "TushareProvider",
    "AKShareProvider",
    "BaoStockProvider",
    "AKSHARE_AVAILABLE",
    "TUSHARE_AVAILABLE",
    "BAOSTOCK_AVAILABLE",
    # 港股
    "ImprovedHKStockProvider",
    "get_improved_hk_provider",
    "HK_PROVIDER_AVAILABLE",
    # 美股
    "YFinanceUtils",
    "OptimizedUSDataProvider",
    "get_data_in_range",
    "YFINANCE_AVAILABLE",
    "OPTIMIZED_US_AVAILABLE",
    "FINNHUB_AVAILABLE",
    # 其他（预留）
    "YahooProvider",
    "FinnhubProvider",
    # 'TDXProvider'  # 已移除
]
