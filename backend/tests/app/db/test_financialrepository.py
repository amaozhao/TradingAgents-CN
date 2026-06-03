from sqlalchemy.dialects import postgresql

from app.db.financialrepository import build_financial_data_query


def test_financial_data_query_filters_split_columns_and_orders_period():
    statement = build_financial_data_query(
        symbol="000001",
        report_period="2025Q4",
        data_source="tushare",
        report_type="quarterly",
        limit=10,
    )
    sql = _compile(statement)

    assert "FROM stock_financial_data" in sql
    assert "stock_financial_data.code =" in sql
    assert "stock_financial_data.report_period =" in sql
    assert "stock_financial_data.data_source =" in sql
    assert "stock_financial_data.payload" in sql
    assert "ORDER BY stock_financial_data.report_period DESC" in sql
    assert "LIMIT" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
