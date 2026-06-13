from sqlalchemy.dialects import postgresql

from app.db.analysis import (
    build_analysis_report_by_analysis_id_select,
    build_analysis_report_by_task_id_select,
    build_user_analysis_reports_count_select,
    build_user_analysis_reports_page_select,
    build_analysis_task_by_task_id_select,
    build_user_analysis_tasks_select,
)


def test_analysis_task_by_task_id_uses_split_task_id():
    sql = _compile(build_analysis_task_by_task_id_select("task-1"))

    assert "FROM analysis_tasks" in sql
    assert "analysis_tasks.task_id =" in sql


def test_analysis_report_by_task_id_uses_split_task_id():
    sql = _compile(build_analysis_report_by_task_id_select("task-1"))

    assert "FROM analysis_reports" in sql
    assert "analysis_reports.task_id =" in sql


def test_analysis_report_by_analysis_id_uses_split_analysis_id():
    sql = _compile(build_analysis_report_by_analysis_id_select("analysis-1"))

    assert "FROM analysis_reports" in sql
    assert "analysis_reports.analysis_id =" in sql


def test_user_analysis_tasks_select_uses_user_status_created_columns():
    sql = _compile(
        build_user_analysis_tasks_select(
            "user-1",
            status="completed",
            limit=20,
            offset=40,
        )
    )

    assert "FROM analysis_tasks" in sql
    assert "analysis_tasks.user_id =" in sql
    assert "analysis_tasks.status =" in sql
    assert "ORDER BY analysis_tasks.created_at DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_user_analysis_tasks_select_filters_batch_id_before_pagination():
    statement = build_user_analysis_tasks_select(
        "user-1",
        status="completed",
        batch_id="batch-1",
        limit=20,
        offset=40,
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "analysis_tasks.payload" in sql
    assert compiled.params["payload_1"] == "batch_id"
    assert compiled.params["param_1"] == "batch-1"
    assert "ORDER BY analysis_tasks.created_at DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def test_user_analysis_reports_page_select_uses_sql_pagination_without_report_body():
    statement = build_user_analysis_reports_page_select(
        user_id="user-1",
        is_admin=False,
        keyword="600519",
        market="A股",
        stock_code=None,
        start_date=None,
        end_date=None,
        limit=20,
        offset=40,
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "FROM analysis_reports" in sql
    assert "analysis_reports.user_id =" in sql
    assert "analysis_reports.analysis_id AS id" in sql
    assert compiled.params["payload_8"] == "deleted"
    assert compiled.params["param_1"] == "true"
    assert "ORDER BY analysis_reports.created_at DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert "reports" not in set(compiled.params.values())


def test_user_analysis_reports_count_select_uses_matching_filters():
    statement = build_user_analysis_reports_count_select(
        user_id="user-1",
        is_admin=False,
        keyword="600519",
        market="A股",
        stock_code="600519",
        start_date="2026-06-01",
        end_date="2026-06-13",
    )
    sql = _compile(statement)

    assert "count" in sql
    assert "FROM analysis_reports" in sql
    assert "analysis_reports.payload" in sql
    assert "deleted" in set(
        statement.compile(dialect=postgresql.dialect()).params.values()
    )
    assert "analysis_reports.user_id =" in sql
    assert "analysis_reports.stock_symbol =" in sql
    assert "analysis_reports.analysis_date >=" in sql
    assert "analysis_reports.analysis_date <=" in sql


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
