# 导入基础模块
from .interface import (
    # Tushare data functions
    get_china_stock_data_tushare,
    # Unified China data functions (recommended)
    get_china_stock_data_unified,
    get_china_stock_fundamentals_tushare,
    get_china_stock_info_unified,
    get_current_china_data_source,
    get_finnhub_company_insider_sentiment,
    get_finnhub_company_insider_transactions,
    # News and sentiment functions
    get_finnhub_news,
    get_google_news,
    # Hong Kong stock functions
    get_hk_stock_data_unified,
    get_hk_stock_info_unified,
    get_reddit_company_news,
    get_reddit_global_news,
    # Financial statements functions
    get_simfin_balance_sheet,
    get_simfin_cashflow,
    get_simfin_income_statements,
    get_stock_data_by_market,
    # Technical analysis functions
    get_stock_stats_indicators_window,
    get_stockstats_indicator,
    get_yfin_data,
    # Market data functions
    get_yfin_data_window,
    switch_china_data_source,
)

# Finnhub 工具（支持新旧路径）
try:
    from .providers.us import get_data_in_range
except ImportError:
    try:
        from .finnhub import get_data_in_range
    except ImportError:
        get_data_in_range = None

# 导入新闻模块（新路径）
try:
    from .news import fetch_top_from_category, get_news_data
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from .news.google import get_news_data
    except ImportError:
        get_news_data = None
    try:
        from .news.reddit import fetch_top_from_category
    except ImportError:
        fetch_top_from_category = None

# 导入日志模块
from trader.utils.logging.manager import get_logger

logger = get_logger("agents")

# 尝试导入yfinance相关模块（支持新旧路径）
try:
    from .providers.us import YFINANCE_AVAILABLE, YFinanceUtils
except ImportError:
    try:
        from .providers.us.yfinance import YFinanceUtils

        YFINANCE_AVAILABLE = True
    except ImportError as e:
        logger.warning(f"⚠️ yfinance模块不可用: {e}")
        YFinanceUtils = None
        YFINANCE_AVAILABLE = False

# 导入技术指标模块（新路径）
try:
    from .technical import STOCKSTATS_AVAILABLE, StockstatsUtils
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from .technical.stats import StockstatsUtils

        STOCKSTATS_AVAILABLE = True
    except ImportError as e:
        logger.warning(f"⚠️ stockstats模块不可用: {e}")
        StockstatsUtils = None
        STOCKSTATS_AVAILABLE = False

__all__ = [
    # News and sentiment functions
    "get_finnhub_news",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_google_news",
    "get_reddit_global_news",
    "get_reddit_company_news",
    # Financial statements functions
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_statements",
    # Technical analysis functions
    "get_stock_stats_indicators_window",
    "get_stockstats_indicator",
    # Market data functions
    "get_yfin_data_window",
    "get_yfin_data",
    # Tushare data functions
    "get_china_stock_data_tushare",
    "get_china_stock_fundamentals_tushare",
    # Unified China data functions
    "get_china_stock_data_unified",
    "get_china_stock_info_unified",
    "switch_china_data_source",
    "get_current_china_data_source",
    # Hong Kong stock functions
    "get_hk_stock_data_unified",
    "get_hk_stock_info_unified",
    "get_stock_data_by_market",
]
