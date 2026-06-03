from sqlalchemy.dialects import postgresql

from app.db.account import (
    build_user_by_legacy_id_select,
    build_user_by_username_select,
    build_user_list_select,
)


def test_user_by_username_select_uses_split_username_and_deleted_columns():
    sql = _compile(build_user_by_username_select("demo"))

    assert "FROM user_accounts" in sql
    assert "user_accounts.deleted IS false" in sql
    assert "user_accounts.username =" in sql


def test_user_by_legacy_id_select_preserves_object_id_compatibility_lookup():
    sql = _compile(build_user_by_legacy_id_select("665ef7c0d9a3a4b2c1d0e9f8"))

    assert "FROM user_accounts" in sql
    assert "user_accounts.legacy_id =" in sql


def test_user_list_select_is_bounded_and_orders_by_created_at():
    sql = _compile(build_user_list_select(skip=20, limit=10))

    assert "FROM user_accounts" in sql
    assert "ORDER BY user_accounts.created_at DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
