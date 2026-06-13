from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.schemas.analysis import AnalysisParameters
from app.schemas.config import UsageRecord


logger = logging.getLogger("app.services.research.agent.stock")

ProviderInfoLoader = Callable[[str, dict[str, dict[str, Any]]], dict[str, Any]]
ConfigLoader = Callable[[], dict[str, Any] | None]
ConfigFilter = Callable[[dict[str, Any] | None], list[dict[str, Any]]]


class StockUsageRecorder:
    def __init__(
        self,
        *,
        provider_info_for_model: ProviderInfoLoader,
        load_config_doc: ConfigLoader,
        enabled_llm_configs: ConfigFilter,
        usage_service: Any,
    ) -> None:
        self._provider_info_for_model = provider_info_for_model
        self._load_config_doc = load_config_doc
        self._enabled_llm_configs = enabled_llm_configs
        self._usage_service = usage_service

    async def record(
        self,
        *,
        task_id: str,
        symbol: str,
        parameters: AnalysisParameters,
        report: dict[str, Any],
    ) -> None:
        model_name = parameters.deep_analysis_model or parameters.quick_analysis_model
        if not model_name:
            return

        try:
            provider_info = self._provider_info_for_model(model_name, {})
            provider = str(provider_info.get("provider") or "unknown")
            input_tokens, output_tokens = usage_token_counts(report)
            pricing = self._usage_pricing_for_model(model_name)
            cost = (
                input_tokens / 1000 * pricing["input_price_per_1k"]
                + output_tokens / 1000 * pricing["output_price_per_1k"]
            )
            record = UsageRecord(
                timestamp=datetime.now().isoformat(),
                provider=provider,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                currency=pricing["currency"],
                session_id=task_id,
                analysis_type="agent_stock_analysis",
                stock_code=symbol,
            )
            await self._usage_service.add_usage_record(record)
        except Exception as exc:
            logger.warning("Agent stock workflow token usage recording failed: %s", exc)

    def _usage_pricing_for_model(self, model_name: str) -> dict[str, Any]:
        config_doc = self._load_config_doc()
        for config in self._enabled_llm_configs(config_doc):
            if str(config.get("model_name") or "") != model_name:
                continue
            return {
                "input_price_per_1k": usage_float(config.get("input_price_per_1k")),
                "output_price_per_1k": usage_float(config.get("output_price_per_1k")),
                "currency": str(config.get("currency") or "CNY"),
            }
        return {
            "input_price_per_1k": 0.0,
            "output_price_per_1k": 0.0,
            "currency": "CNY",
        }


def usage_token_counts(report: dict[str, Any]) -> tuple[int, int]:
    raw_tokens = report.get("tokens_used")
    try:
        total_tokens = int(raw_tokens or 0)
    except (TypeError, ValueError):
        total_tokens = 0
    if total_tokens > 0:
        input_tokens = max(total_tokens // 2, 1)
        return input_tokens, max(total_tokens - input_tokens, 1)

    text_parts: list[str] = [
        str(report.get("summary") or ""),
        str(report.get("recommendation") or ""),
    ]
    decision = report.get("decision")
    if isinstance(decision, dict):
        text_parts.append(str(decision.get("reasoning") or ""))
    reports = report.get("reports")
    if isinstance(reports, dict):
        text_parts.extend(str(value) for value in reports.values())
    output_tokens = max(sum(len(part) for part in text_parts) // 4, 1)
    return max(output_tokens * 2, 1), output_tokens


def usage_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
