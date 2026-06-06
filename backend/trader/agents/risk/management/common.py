import queue
import threading
from types import SimpleNamespace
from typing import Any

from trader.utils.logging.init import get_logger

logger = get_logger("default")

DEFAULT_RISK_LLM_TIMEOUT_SECONDS = 300.0
MIN_RISK_LLM_TIMEOUT_SECONDS = 1.0


def _coerce_timeout_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, tuple):
        values = [item for item in value if isinstance(item, (int, float))]
        return float(max(values)) if values else None
    if isinstance(value, int | float):
        return float(value)
    return None


def get_risk_llm_timeout_seconds(llm) -> float:
    explicit_risk_timeout = _coerce_timeout_seconds(
        getattr(llm, "risk_timeout_seconds", None)
    )
    if explicit_risk_timeout and explicit_risk_timeout > 0:
        return min(explicit_risk_timeout, DEFAULT_RISK_LLM_TIMEOUT_SECONDS)

    configured = _coerce_timeout_seconds(
        getattr(llm, "request_timeout", None)
    ) or _coerce_timeout_seconds(getattr(llm, "timeout", None))
    if configured and configured >= MIN_RISK_LLM_TIMEOUT_SECONDS:
        return min(configured, DEFAULT_RISK_LLM_TIMEOUT_SECONDS)
    return DEFAULT_RISK_LLM_TIMEOUT_SECONDS


def invoke_risk_llm_with_timeout(
    llm,
    prompt: str,
    *,
    analyst_name: str,
    fallback_content: str,
):
    timeout_seconds = get_risk_llm_timeout_seconds(llm)
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def invoke_llm():
        try:
            result_queue.put(("ok", llm.invoke(prompt)), block=False)
        except Exception as exc:
            result_queue.put(("error", exc), block=False)

    thread = threading.Thread(
        target=invoke_llm,
        name=f"{analyst_name.lower().replace(' ', '-')}-llm",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        logger.error(
            "⏱️ [%s] LLM调用超过 %.1f 秒，使用风险阶段兜底内容继续分析",
            analyst_name,
            timeout_seconds,
        )
        return SimpleNamespace(content=fallback_content)

    status, payload = result_queue.get_nowait()
    if status == "error":
        raise payload
    return payload


def invoke_with_timeout(
    fn,
    *,
    timeout_seconds: float = DEFAULT_RISK_LLM_TIMEOUT_SECONDS,
    operation_name: str,
    fallback_value: Any,
):
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def run_operation():
        try:
            result_queue.put(("ok", fn()), block=False)
        except Exception as exc:
            result_queue.put(("error", exc), block=False)

    thread = threading.Thread(
        target=run_operation,
        name=f"{operation_name.lower().replace(' ', '-')}-timeout",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        logger.error(
            "⏱️ [%s] 执行超过 %.1f 秒，使用兜底结果继续分析",
            operation_name,
            timeout_seconds,
        )
        return fallback_value

    status, payload = result_queue.get_nowait()
    if status == "error":
        raise payload
    return payload
