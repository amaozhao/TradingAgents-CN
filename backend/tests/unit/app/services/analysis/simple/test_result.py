from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple.result import build_analysis_result


def test_build_analysis_result_serializes_langchain_messages() -> None:
    request = SingleAnalysisRequest(
        symbol="600519",
        parameters=AnalysisParameters(selected_analysts=["market"]),
    )
    state = {
        "messages": [HumanMessage(content="Analyze 600519")],
        "final_trade_decision": "Final trade decision with enough detail to persist.",
    }
    decision = {
        "action": "HOLD",
        "confidence": 0.7,
        "risk_score": 0.4,
        "reasoning": "Risk reward is balanced.",
        "messages": [HumanMessage(content="Decision context")],
    }

    result = build_analysis_result(
        request=request,
        analysis_date="2026-06-15",
        state=state,
        decision=decision,
        execution_time=1.2,
        task_id="task-1",
    )

    json.dumps(result)
    assert result["state"]["messages"] == [
        {"type": "human", "content": "Analyze 600519"}
    ]
    assert result["detailed_analysis"]["messages"] == [
        {"type": "human", "content": "Decision context"}
    ]
