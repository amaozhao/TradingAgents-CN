import pytest
from langchain_core.messages import AIMessage

from app.services.research.agent.flow.stages.conditions import WorkflowConditionAdapter
from trader.graph.conditions import ConditionalLogic


def _message_state(
    *,
    report_key: str,
    report: str = "",
    tool_count_key: str,
    tool_count: int = 0,
    tool_calls: bool = False,
):
    calls = (
        [{"name": "tool", "args": {"symbol": "600519"}, "id": "call-1"}]
        if tool_calls
        else []
    )
    return {
        "messages": [AIMessage(content="", tool_calls=calls)],
        report_key: report,
        tool_count_key: tool_count,
    }


@pytest.mark.parametrize(
    ("method", "state"),
    [
        (
            "should_continue_market",
            _message_state(
                report_key="market_report",
                tool_count_key="market_tool_call_count",
            ),
        ),
        (
            "should_continue_market",
            _message_state(
                report_key="market_report",
                tool_count_key="market_tool_call_count",
                tool_calls=True,
            ),
        ),
        (
            "should_continue_market",
            _message_state(
                report_key="market_report",
                report="M" * 101,
                tool_count_key="market_tool_call_count",
            ),
        ),
        (
            "should_continue_social",
            _message_state(
                report_key="sentiment_report",
                tool_count_key="sentiment_tool_call_count",
                tool_count=3,
                tool_calls=True,
            ),
        ),
        (
            "should_continue_news",
            _message_state(
                report_key="news_report",
                tool_count_key="news_tool_call_count",
                tool_calls=True,
            ),
        ),
        (
            "should_continue_fundamentals",
            _message_state(
                report_key="fundamentals_report",
                tool_count_key="fundamentals_tool_call_count",
                tool_count=1,
                tool_calls=True,
            ),
        ),
    ],
)
def test_analyst_conditions_match_old_logic(method, state):
    old = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
    new = WorkflowConditionAdapter(old)

    assert getattr(new, method)(state) == getattr(old, method)(state)


@pytest.mark.parametrize(
    "state",
    [
        {"investment_debate_state": {"count": 1, "current_response": "Bull says"}},
        {"investment_debate_state": {"count": 1, "current_response": "Bear says"}},
        {"investment_debate_state": {"count": 2, "current_response": "Bull says"}},
    ],
)
def test_debate_condition_matches_old_logic(state):
    old = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
    new = WorkflowConditionAdapter(old)

    assert new.should_continue_debate(state) == old.should_continue_debate(state)


@pytest.mark.parametrize(
    "state",
    [
        {"risk_debate_state": {"count": 0, "latest_speaker": ""}},
        {"risk_debate_state": {"count": 1, "latest_speaker": "Risky"}},
        {"risk_debate_state": {"count": 2, "latest_speaker": "Safe"}},
        {"risk_debate_state": {"count": 3, "latest_speaker": "Neutral"}},
    ],
)
def test_risk_condition_matches_old_logic(state):
    old = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
    new = WorkflowConditionAdapter(old)

    assert new.should_continue_risk_analysis(state) == (
        old.should_continue_risk_analysis(state)
    )
