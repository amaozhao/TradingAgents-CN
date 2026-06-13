from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.analysis import AnalysisParameters

from .stage import planned_stock_stages


ModelResolver = Callable[[dict[str, Any]], tuple[str | None, str | None]]


_ANALYST_NAME_TO_ID = {
    "市场分析师": "market",
    "基本面分析师": "fundamentals",
    "新闻分析师": "news",
    "社媒分析师": "social",
    "社交媒体分析师": "social",
}

_DEPTH_TO_LABEL = {
    1: "快速",
    2: "基础",
    3: "标准",
    4: "深度",
    5: "全面",
    "1": "快速",
    "2": "基础",
    "3": "标准",
    "4": "深度",
    "5": "全面",
    "快速": "快速",
    "基础": "基础",
    "标准": "标准",
    "深度": "深度",
    "全面": "全面",
}


@dataclass(frozen=True)
class StockAnalysisCommand:
    raw_symbol: Any
    symbol: str
    market_type: str
    parameters: AnalysisParameters
    skipped_stages: list[dict[str, str]]
    stage_plan: list[dict[str, str]]

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        *,
        resolve_models: ModelResolver,
    ) -> "StockAnalysisCommand":
        raw_symbol = payload.get("symbol") or payload.get("stock_code")
        symbol, market_type = normalize_stock_symbol_for_analysis(
            raw_symbol, payload.get("market_type")
        )
        parameter_payload = {**payload, "market_type": market_type}
        parameters, skipped_stages, stage_plan = analysis_parameters(
            parameter_payload,
            resolve_models=resolve_models,
        )
        return cls(
            raw_symbol=raw_symbol,
            symbol=symbol,
            market_type=market_type,
            parameters=parameters,
            skipped_stages=skipped_stages,
            stage_plan=stage_plan,
        )

    def symbol_format_error(self) -> str | None:
        return stock_symbol_format_error(
            self.raw_symbol, self.symbol, self.parameters.market_type
        )


def normalize_requested_market(raw: Any) -> str | None:
    value = str(raw or "").strip().upper()
    if not value:
        return None
    if raw == "港股" or value in {"HK", "HKEX", "HKG"}:
        return "港股"
    if raw == "美股" or value in {"US", "USA", "NASDAQ", "NYSE", "AMEX"}:
        return "美股"
    if raw == "A股" or value in {"A", "ASHARE", "A-SHARE", "CN", "CHINA"}:
        return "A股"
    return None


def normalize_stock_symbol_for_analysis(
    raw: Any, market_type: str | None
) -> tuple[str, str]:
    symbol = str(raw or "").strip().upper()
    if not symbol:
        return "", normalize_requested_market(market_type) or "A股"

    requested_market = normalize_requested_market(market_type)

    a_share_prefix_match = re.match(r"^(SH|SZ|BJ|SSE|SZSE|BSE)(\d{6})$", symbol)
    if a_share_prefix_match:
        return a_share_prefix_match.group(2), "A股"
    a_share_suffix_match = re.match(r"^(\d{6})\.(SH|SZ|BJ|SSE|SZSE|BSE)$", symbol)
    if a_share_suffix_match:
        return a_share_suffix_match.group(1), "A股"
    if re.match(r"^\d{6}$", symbol):
        return symbol, requested_market or "A股"

    hk_prefix_match = re.match(r"^HK(\d{1,5})$", symbol)
    if hk_prefix_match:
        return hk_prefix_match.group(1), "港股"
    hk_suffix_match = re.match(r"^(\d{1,5})\.HK$", symbol)
    if hk_suffix_match:
        return hk_suffix_match.group(1), "港股"
    if re.match(r"^\d{1,5}$", symbol):
        return symbol, requested_market or "港股"

    us_suffix_match = re.match(r"^([A-Z]{1,5})\.(US|NASDAQ|NYSE|AMEX)$", symbol)
    if us_suffix_match:
        return us_suffix_match.group(1), "美股"
    if re.match(r"^[A-Z]{1,5}$", symbol):
        return symbol, requested_market or "美股"

    return symbol, requested_market or "A股"


def stock_symbol_format_error(
    raw_symbol: Any, symbol: str, market_type: str
) -> str | None:
    if market_type == "A股" and not re.match(r"^\d{6}$", symbol):
        return f"A股代码格式错误：{raw_symbol}。Agent 已支持 600519、600519.SH、SH600519 格式。"
    if market_type == "港股" and not re.match(r"^\d{1,5}$", symbol):
        return (
            f"港股代码格式错误：{raw_symbol}。Agent 已支持 700、0700.HK、HK09988 格式。"
        )
    if market_type == "美股" and not re.match(r"^[A-Z]{1,5}$", symbol):
        return (
            f"美股代码格式错误：{raw_symbol}。Agent 已支持 AAPL、TSLA、AAPL.US 格式。"
        )
    return None


def normalize_analysts(
    raw: Any, *, market_type: str
) -> tuple[list[str], list[dict[str, str]]]:
    if not raw:
        return ["market", "fundamentals"], []
    values = raw if isinstance(raw, list) else [raw]
    analysts: list[str] = []
    skipped: list[dict[str, str]] = []
    for value in values:
        key = str(value).strip()
        normalized = _ANALYST_NAME_TO_ID.get(key, key)
        if normalized == "social" and market_type == "A股":
            skipped.append(
                {
                    "stage": "social_analysis",
                    "reason": "A 股默认禁用社媒分析。",
                }
            )
            continue
        if normalized in {"market", "fundamentals", "news", "social"}:
            analysts.append(normalized)
    return analysts or ["market", "fundamentals"], skipped


def normalize_depth(raw: Any) -> str:
    if raw is None:
        return "标准"
    return _DEPTH_TO_LABEL.get(raw, _DEPTH_TO_LABEL.get(str(raw).strip(), "标准"))


def analysis_parameters(
    payload: dict[str, Any],
    *,
    resolve_models: ModelResolver,
) -> tuple[AnalysisParameters, list[dict[str, str]], list[dict[str, str]]]:
    quick_model, deep_model = resolve_models(payload)
    market_type = str(payload.get("market_type") or "A股")
    analysts, skipped_stages = normalize_analysts(
        payload.get("selected_analysts") or payload.get("analysts"),
        market_type=market_type,
    )
    include_risk = bool(payload.get("include_risk", True))
    stage_plan = planned_stock_stages(
        selected_analysts=analysts,
        include_risk=include_risk,
        initial_skipped=skipped_stages,
    )
    skipped_stages = [
        {"stage": item["stage"], "reason": item["reason"]}
        for item in stage_plan
        if item.get("status") == "skipped" and item.get("reason")
    ]
    return (
        AnalysisParameters.model_validate(
            {
                "market_type": market_type,
                "analysis_date": payload.get("analysis_date"),
                "research_depth": normalize_depth(
                    payload.get("research_depth") or payload.get("depth")
                ),
                "selected_analysts": analysts,
                "custom_prompt": payload.get("custom_prompt"),
                "include_sentiment": bool(payload.get("include_sentiment", True)),
                "include_risk": include_risk,
                "language": payload.get("language") or "zh-CN",
                "quick_analysis_model": quick_model,
                "deep_analysis_model": deep_model,
            }
        ),
        skipped_stages,
        stage_plan,
    )
