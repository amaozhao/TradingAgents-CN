from datetime import datetime

from sqlalchemy.dialects import postgresql

from app.db.news import build_news_select
from app.services.market.news import NewsQueryParams


def test_news_select_filters_split_columns_for_common_query():
    params = NewsQueryParams(
        symbol="000001",
        start_time=datetime(2026, 6, 1),
        end_time=datetime(2026, 6, 3),
        category="company",
        sentiment="positive",
        importance="high",
        data_source="akshare",
        limit=20,
        skip=10,
    )

    sql = str(build_news_select(params).compile(dialect=postgresql.dialect()))

    assert "FROM stock_news" in sql
    assert "stock_news.deleted IS false" in sql
    assert "stock_news.symbol =" in sql
    assert "stock_news.publish_time >=" in sql
    assert "stock_news.publish_time <=" in sql
    assert "stock_news.category =" in sql
    assert "stock_news.sentiment =" in sql
    assert "stock_news.importance =" in sql
    assert "stock_news.data_source =" in sql
    assert "ORDER BY stock_news.publish_time DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql
