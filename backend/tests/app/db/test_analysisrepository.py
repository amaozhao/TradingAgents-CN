from sqlalchemy.dialects import postgresql

from app.db.analysisrepository import (
    build_analysis_report_by_analysis_id_select,
    build_analysis_report_by_task_id_select,
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


def _compile(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))
