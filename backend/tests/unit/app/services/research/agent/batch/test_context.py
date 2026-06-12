import pytest

from app.schemas.analysis import AnalysisParameters
from app.services.research.agent.batch import context as batch_context
from app.services.research.agent.batch.context import (
    BatchConfigError,
    build_batch_request_context,
)
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext


def _tool_context() -> ToolExecutionContext:
    principal = ResearchPrincipal.from_user(
        {"id": "user-1", "username": "alice", "is_admin": False, "roles": []},
        session_id="session-1",
    )
    return ToolExecutionContext(principal=principal, session_id="session-1")


@pytest.fixture(autouse=True)
def _analysis_parameters(monkeypatch):
    def fake_analysis_parameters(payload):
        return (
            AnalysisParameters(
                market_type=payload.get("market_type") or "A股",
                analysis_date=payload.get("analysis_date"),
                research_depth=payload.get("research_depth") or "标准",
                selected_analysts=payload.get("selected_analysts")
                or ["market", "fundamentals"],
                include_sentiment=payload.get("include_sentiment", True),
                include_risk=payload.get("include_risk", True),
                language=payload.get("language") or "zh-CN",
                quick_analysis_model=payload.get("quick_analysis_model") or "quick",
                deep_analysis_model=payload.get("deep_analysis_model") or "deep",
            ),
            [],
            [],
        )

    monkeypatch.setattr(batch_context, "_analysis_parameters", fake_analysis_parameters)


def test_missing_symbols_returns_config_error():
    with pytest.raises(BatchConfigError) as exc_info:
        build_batch_request_context(_tool_context(), {"title": "批量分析"})

    assert exc_info.value.missing == ["symbols"]
    assert "symbols or stock_codes" in exc_info.value.reason


def test_empty_symbols_returns_config_error():
    with pytest.raises(BatchConfigError) as exc_info:
        build_batch_request_context(_tool_context(), {"title": "批量分析", "symbols": []})

    assert exc_info.value.missing == ["symbols"]
    assert "1-10" in exc_info.value.instruction


def test_more_than_ten_symbols_returns_config_error():
    payload = {"title": "批量分析", "symbols": [f"6000{index:02d}" for index in range(11)]}

    with pytest.raises(BatchConfigError) as exc_info:
        build_batch_request_context(_tool_context(), payload)

    assert exc_info.value.missing == ["symbols"]
    assert "最多 10" in exc_info.value.reason


def test_symbols_take_precedence_over_stock_codes_and_deduplicate_in_order():
    context = build_batch_request_context(
        _tool_context(),
        {
            "title": "批量分析",
            "symbols": ["SH600036", "600036", "000001"],
            "stock_codes": ["300001"],
        },
    )

    assert context.user_id == "user-1"
    assert context.title == "批量分析"
    assert context.symbols == ("600036", "000001")
    assert context.skipped_symbols == ()
    assert context.wait_for_completion is False


def test_stock_codes_compatibility_field_is_accepted():
    context = build_batch_request_context(
        _tool_context(),
        {"title": "批量分析", "stock_codes": ["000001", "000002"]},
    )

    assert context.symbols == ("000001", "000002")


def test_invalid_symbol_strict_true_returns_config_error():
    with pytest.raises(BatchConfigError) as exc_info:
        build_batch_request_context(
            _tool_context(),
            {
                "title": "批量分析",
                "symbols": ["600036", "bad-symbol"],
                "strict_symbols": True,
            },
        )

    assert exc_info.value.missing == ["symbols"]
    assert "bad-symbol" in exc_info.value.reason


def test_invalid_symbol_strict_false_skips_invalid_symbol():
    context = build_batch_request_context(
        _tool_context(),
        {
            "title": "批量分析",
            "symbols": ["600036", "bad-symbol", "000001"],
            "strict_symbols": False,
        },
    )

    assert context.symbols == ("600036", "000001")
    assert context.skipped_symbols == ("bad-symbol",)


def test_max_concurrency_is_bounded_by_system_limit():
    context = build_batch_request_context(
        _tool_context(),
        {
            "title": "批量分析",
            "symbols": ["600036", "000001"],
            "max_concurrency": 99,
            "wait_for_completion": True,
        },
        system_max_concurrency=4,
    )

    assert context.max_concurrency == 4
    assert context.wait_for_completion is True
