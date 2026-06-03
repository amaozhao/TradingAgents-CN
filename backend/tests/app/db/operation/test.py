from sqlalchemy.dialects import postgresql

from app.db.operation import (
    build_operation_log_action_distribution_select,
    build_operation_log_count,
    build_operation_log_hourly_distribution_select,
    build_operation_log_select,
    build_operation_log_totals_select,
)
from app.models.operations import OperationLogQuery


def test_operation_log_select_filters_split_columns_for_log_page():
    query = OperationLogQuery(
        page=2,
        page_size=25,
        start_date="2026-06-01T00:00:00",
        end_date="2026-06-03T23:59:59",
        action_type="user_login",
        success=True,
        user_id="user-1",
    )

    sql = _compile(build_operation_log_select(query, offset=25, limit=25))

    assert "FROM operation_logs" in sql
    assert "operation_logs.deleted IS false" in sql
    assert "operation_logs.timestamp >=" in sql
    assert "operation_logs.timestamp <=" in sql
    assert "operation_logs.action_type =" in sql
    assert "operation_logs.success = true" in sql
    assert "operation_logs.user_id =" in sql
    assert "ORDER BY operation_logs.timestamp DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_operation_log_count_uses_same_split_filters_without_ordering():
    query = OperationLogQuery(action_type="data_import", success=False)

    sql = _compile(build_operation_log_count(query))

    assert "count(*)" in sql
    assert "operation_logs.action_type =" in sql
    assert "operation_logs.success = false" in sql
    assert "ORDER BY" not in sql


def test_operation_log_stats_uses_split_timestamp_success_and_action_columns():
    totals_sql = _compile(build_operation_log_totals_select(days=7))
    action_sql = _compile(build_operation_log_action_distribution_select(days=7))
    hourly_sql = _compile(build_operation_log_hourly_distribution_select(days=7))

    assert "FROM operation_logs" in totals_sql
    assert "operation_logs.deleted IS false" in totals_sql
    assert "operation_logs.timestamp >=" in totals_sql
    assert "operation_logs.success IS true" in totals_sql

    assert "GROUP BY operation_logs.action_type" in action_sql
    assert "ORDER BY count(*) DESC" in action_sql

    assert "EXTRACT(hour FROM operation_logs.timestamp)" in hourly_sql
    assert "GROUP BY EXTRACT(hour FROM operation_logs.timestamp)" in hourly_sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
