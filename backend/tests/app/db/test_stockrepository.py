from sqlalchemy.dialects import postgresql

from app.db.stockrepository import (
    build_get_market_quote,
    build_get_stock_basic_info,
    build_search_stocks,
    build_stock_list,
)


def test_get_stock_basic_info_filters_code_and_source_priority():
    statement = build_get_stock_basic_info("000001", source="tushare")
    sql = _compile(statement)

    assert "FROM stock_basic_info" in sql
    assert "stock_basic_info.code =" in sql
    assert "stock_basic_info.source =" in sql
    assert "LIMIT" in sql


def test_get_market_quote_filters_code_and_orders_by_updated_at():
    statement = build_get_market_quote("000001")
    sql = _compile(statement)

    assert "FROM market_quotes" in sql
    assert "market_quotes.code =" in sql
    assert "ORDER BY market_quotes.updated_at DESC" in sql
    assert "LIMIT" in sql


def test_stock_list_filters_split_columns_and_pages():
    statement = build_stock_list(
        source="akshare",
        market="主板",
        industry="银行",
        page=2,
        page_size=20,
    )
    sql = _compile(statement)

    assert "FROM stock_basic_info" in sql
    assert "stock_basic_info.source =" in sql
    assert "stock_basic_info.market =" in sql
    assert "stock_basic_info.industry =" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_search_stocks_filters_code_and_name_split_columns():
    statement = build_search_stocks("000001", limit=5)
    sql = _compile(statement)

    assert "FROM stock_basic_info" in sql
    assert "stock_basic_info.code ILIKE" in sql
    assert "stock_basic_info.name ILIKE" in sql
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert "payload" not in where_clause
    assert "LIMIT" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
