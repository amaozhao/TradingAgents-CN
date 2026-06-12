from sqlalchemy.dialects import postgresql

from app.db.preference import build_user_favorites_select, build_user_tags_select


def test_user_favorites_select_filters_user_and_deleted_split_columns():
    sql = str(
        build_user_favorites_select("user-1").compile(dialect=postgresql.dialect())
    )

    assert "FROM user_favorites" in sql
    assert "user_favorites.user_id =" in sql
    assert "user_favorites.deleted IS false" in sql
    assert "ORDER BY user_favorites.created_at DESC" in sql


def test_user_tags_select_filters_user_and_orders_by_split_columns():
    sql = str(build_user_tags_select("user-1").compile(dialect=postgresql.dialect()))

    assert "FROM user_tags" in sql
    assert "user_tags.user_id =" in sql
    assert "user_tags.deleted IS false" in sql
    assert "ORDER BY user_tags.sort_order ASC, user_tags.name ASC" in sql
