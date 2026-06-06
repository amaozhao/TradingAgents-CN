from __future__ import annotations

from app.routers import analysis


def test_completed_postgres_task_uses_stored_message_and_step():
    task_result = {"message": "分析完成", "current_step": "completed"}

    assert (
        analysis._status_message_from_task_result(task_result, "completed", None)
        == "分析完成"
    )
    assert analysis._status_step_from_task_result(task_result, "completed") == "completed"


def test_completed_postgres_task_defaults_to_completion_message():
    assert analysis._status_message_from_task_result({}, "completed", None) == "分析完成"
    assert analysis._status_step_from_task_result({}, "completed") == "completed"


def test_failed_postgres_task_prefers_error_message_when_no_stored_message():
    assert (
        analysis._status_message_from_task_result({}, "failed", "LLM请求超时")
        == "LLM请求超时"
    )
    assert analysis._status_step_from_task_result({}, "failed") == "failed"
