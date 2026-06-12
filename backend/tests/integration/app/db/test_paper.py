from sqlalchemy.dialects import postgresql

from app.db.paper import (
    build_paper_account_select,
    build_paper_orders_select,
    build_paper_positions_select,
)


def test_paper_account_select_uses_user_id_and_deleted_split_columns():
    sql = _compile(build_paper_account_select("user-1"))

    assert "FROM paper_accounts" in sql
    assert "paper_accounts.deleted IS false" in sql
    assert "paper_accounts.user_id =" in sql


def test_paper_positions_select_uses_user_id_and_deleted_split_columns():
    sql = _compile(build_paper_positions_select("user-1"))

    assert "FROM paper_positions" in sql
    assert "paper_positions.deleted IS false" in sql
    assert "paper_positions.user_id =" in sql


def test_paper_orders_select_orders_by_created_at_split_column():
    sql = _compile(build_paper_orders_select("user-1", limit=50))

    assert "FROM paper_orders" in sql
    assert "paper_orders.deleted IS false" in sql
    assert "paper_orders.user_id =" in sql
    assert "ORDER BY paper_orders.created_at DESC" in sql
    assert "LIMIT" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
