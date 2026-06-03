from sqlalchemy.dialects import postgresql

from app.db.stock_repository import build_list_stock_daily_quotes
from app.db.screening_repository import build_screening_count, build_screening_select


def test_screening_select_joins_hot_tables_and_filters_split_columns():
    statement = build_screening_select(
        conditions=[
            {"field": "industry", "operator": "contains", "value": "银行"},
            {"field": "total_mv", "operator": ">=", "value": 100},
            {"field": "pct_chg", "operator": "between", "value": [1, 5]},
        ],
        limit=20,
        offset=10,
        order_by=[{"field": "amount", "direction": "desc"}],
        source="akshare",
    )

    sql = _compile(statement)

    assert "FROM stock_basic_info" in sql
    assert "LEFT OUTER JOIN market_quotes" in sql
    assert "LEFT OUTER JOIN stock_financial_data" in sql
    assert "stock_basic_info.industry ILIKE" in sql
    assert "stock_basic_info.total_mv >=" in sql
    assert "market_quotes.pct_chg >=" in sql
    assert "ORDER BY market_quotes.amount DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_screening_count_uses_same_filters_without_ordering():
    statement = build_screening_count(
        conditions=[{"field": "pe", "operator": "<", "value": 20}],
        source="tushare",
    )

    sql = _compile(statement)

    assert "count(*)" in sql
    assert "stock_basic_info.pe <" in sql
    assert "ORDER BY" not in sql


def test_daily_quotes_select_filters_split_history_columns():
    statement = build_list_stock_daily_quotes(
        market="HK",
        code="00700",
        start_date="2026-01-01",
        end_date="2026-06-03",
        data_source="akshare",
        period="daily",
        limit=50,
    )

    sql = _compile(statement)

    assert "FROM stock_daily_quotes" in sql
    assert "stock_daily_quotes.trade_date >=" in sql
    assert "stock_daily_quotes.trade_date <=" in sql
    assert "stock_daily_quotes.market =" in sql
    assert "stock_daily_quotes.data_source =" in sql
    assert "stock_daily_quotes.period =" in sql
    assert "ORDER BY stock_daily_quotes.trade_date DESC" in sql
    assert "LIMIT" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
