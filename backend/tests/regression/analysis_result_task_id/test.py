from types import SimpleNamespace

from app.services.analysis.simple.result import build_analysis_result


def _request():
    return SimpleNamespace(
        stock_code="600519",
        parameters=SimpleNamespace(
            selected_analysts=["market", "fundamentals"],
            research_depth="3",
        ),
    )


def test_build_analysis_result_accepts_task_id_for_completion_logging():
    result = build_analysis_result(
        request=_request(),
        analysis_date="2026-06-06",
        state={
            "final_trade_decision": "建议持有，等待更多确定性信号。" * 5,
            "performance_metrics": {"total_elapsed": 1.2},
        },
        decision={"action": "HOLD", "reasoning": "估值和风险均衡"},
        execution_time=1.2,
        task_id="task-123",
    )

    assert result["stock_code"] == "600519"
    assert result["decision"]["action"] == "持有"


def test_build_analysis_result_without_task_id_does_not_raise_name_error():
    result = build_analysis_result(
        request=_request(),
        analysis_date="2026-06-06",
        state={"final_trade_decision": "建议持有，等待更多确定性信号。" * 5},
        decision={"action": "HOLD", "reasoning": "估值和风险均衡"},
        execution_time=1.2,
    )

    assert result["analysis_id"]
