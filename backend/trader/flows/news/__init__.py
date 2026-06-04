"""
新闻数据获取模块
统一管理各种新闻数据源
"""

# 导入 Google News
try:
    from .google import get_news_data

    GOOGLE_NEWS_AVAILABLE = True
except ImportError:
    get_news_data = None
    GOOGLE_NEWS_AVAILABLE = False

# 导入 Reddit
try:
    from .reddit import fetch_top_from_category

    REDDIT_AVAILABLE = True
except ImportError:
    fetch_top_from_category = None
    REDDIT_AVAILABLE = False

# 导入实时新闻
try:
    from .real.time import get_realtime_stock_news as get_realtime_news

    get_news_with_sentiment = None
    search_news_by_keyword = None
    REALTIME_NEWS_AVAILABLE = True
except ImportError:
    get_realtime_news = None
    get_news_with_sentiment = None
    search_news_by_keyword = None
    REALTIME_NEWS_AVAILABLE = False

# 导入中国财经数据聚合器
try:
    from .china import ChineseFinanceDataAggregator

    CHINESE_FINANCE_AVAILABLE = True
except ImportError:
    ChineseFinanceDataAggregator = None
    CHINESE_FINANCE_AVAILABLE = False

__all__ = [
    # Google News
    "get_news_data",
    "GOOGLE_NEWS_AVAILABLE",
    # Reddit
    "fetch_top_from_category",
    "REDDIT_AVAILABLE",
    # Realtime News
    "get_realtime_news",
    "get_news_with_sentiment",
    "search_news_by_keyword",
    "REALTIME_NEWS_AVAILABLE",
    # Chinese Finance
    "ChineseFinanceDataAggregator",
    "CHINESE_FINANCE_AVAILABLE",
]
