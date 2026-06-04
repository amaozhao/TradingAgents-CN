from .base import NewsBaseMixin
from .query import NewsQueryMixin
from .search import NewsSearchMixin
from .stats import NewsStatsMixin
from .write import NewsWriteMixin


class NewsDataService(
    NewsBaseMixin,
    NewsWriteMixin,
    NewsQueryMixin,
    NewsStatsMixin,
    NewsSearchMixin,
):
    """新闻数据服务"""
