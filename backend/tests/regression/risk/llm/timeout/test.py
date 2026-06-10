import time

from trader.agents.risk.management.common import (
    DEFAULT_RISK_LLM_TIMEOUT_SECONDS,
    get_risk_llm_timeout_seconds,
    invoke_risk_llm_with_timeout,
    invoke_with_timeout,
)


class HangingLlm:
    risk_timeout_seconds = 0.01

    def invoke(self, _prompt):
        time.sleep(0.2)
        raise AssertionError("invoke should have timed out before this returns")


def test_risk_llm_timeout_returns_fallback_without_waiting_for_invoke():
    start = time.monotonic()

    response = invoke_risk_llm_with_timeout(
        HangingLlm(),
        "prompt",
        analyst_name="Neutral Analyst",
        fallback_content="fallback risk response",
    )

    assert response.content == "fallback risk response"
    assert time.monotonic() - start < 0.15


def test_generic_timeout_returns_fallback_without_waiting_for_callable():
    start = time.monotonic()

    value = invoke_with_timeout(
        lambda: time.sleep(0.2),
        timeout_seconds=0.01,
        operation_name="Research Manager",
        fallback_value="fallback plan",
    )

    assert value == "fallback plan"
    assert time.monotonic() - start < 0.15


def test_tiny_configured_llm_timeout_is_treated_as_invalid():
    class TinyTimeoutLlm:
        timeout = 1e-12

    assert get_risk_llm_timeout_seconds(TinyTimeoutLlm()) == (
        DEFAULT_RISK_LLM_TIMEOUT_SECONDS
    )
