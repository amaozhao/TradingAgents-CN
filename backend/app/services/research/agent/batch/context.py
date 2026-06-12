from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.schemas.analysis import AnalysisParameters

from ..context import ToolExecutionContext


@dataclass(frozen=True)
class BatchConfigError(ValueError):
    missing: list[str]
    reason: str
    instruction: str


@dataclass(frozen=True)
class BatchRequestContext:
    user_id: str
    title: str
    description: str | None
    symbols: tuple[str, ...]
    skipped_symbols: tuple[str, ...]
    parameters: AnalysisParameters
    skipped_stages: tuple[dict[str, str], ...]
    stage_plan: tuple[dict[str, str], ...]
    strict_symbols: bool
    max_concurrency: int
    wait_for_completion: bool
    raw_payload: Mapping[str, object]


def build_batch_request_context(
    context: ToolExecutionContext,
    payload: Mapping[str, object],
    *,
    system_max_concurrency: int = 3,
) -> BatchRequestContext:
    raw_symbols = _raw_symbols(payload)
    if raw_symbols is None or len(raw_symbols) == 0:
        raise BatchConfigError(
            missing=["symbols"],
            reason="Missing required argument: symbols or stock_codes.",
            instruction="请提供 1-10 个股票代码。",
        )
    if len(raw_symbols) > 10:
        raise BatchConfigError(
            missing=["symbols"],
            reason="批量分析最多 10 只股票。",
            instruction="请提供 1-10 个股票代码。",
        )

    parameters, skipped_stages, stage_plan = _analysis_parameters(dict(payload))
    strict_symbols = bool(payload.get("strict_symbols", True))
    symbols, skipped = _normalize_symbols(
        raw_symbols,
        market_type=parameters.market_type,
        strict_symbols=strict_symbols,
    )
    if not symbols:
        raise BatchConfigError(
            missing=["symbols"],
            reason="No valid stock symbols were provided.",
            instruction="请提供 1-10 个有效股票代码。",
        )

    return BatchRequestContext(
        user_id=context.principal.user_id,
        title=str(payload.get("title") or "批量分析"),
        description=_optional_string(payload.get("description")),
        symbols=tuple(symbols),
        skipped_symbols=tuple(skipped),
        parameters=parameters,
        skipped_stages=tuple(skipped_stages),
        stage_plan=tuple(stage_plan),
        strict_symbols=strict_symbols,
        max_concurrency=_bounded_concurrency(
            payload.get("max_concurrency"),
            system_max_concurrency=system_max_concurrency,
        ),
        wait_for_completion=bool(payload.get("wait_for_completion", False)),
        raw_payload=dict(payload),
    )


def _raw_symbols(payload: Mapping[str, object]) -> list[object] | None:
    raw = payload.get("symbols")
    if raw is None:
        raw = payload.get("stock_codes")
    if raw is None:
        return None
    if isinstance(raw, (str, bytes)):
        return [raw]
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, tuple):
        return list(raw)
    return [raw]


def _analysis_parameters(payload: dict[str, Any]) -> tuple[AnalysisParameters, list[str], list[str]]:
    from ..stock import _analysis_parameters as stock_analysis_parameters

    return stock_analysis_parameters(payload)


def _normalize_stock_symbol_for_analysis(
    raw_symbol: object,
    market_type: str | None,
) -> tuple[str, str]:
    symbol = str(raw_symbol or "").strip().upper()
    if not symbol:
        return "", _normalize_requested_market(market_type) or "A股"

    requested_market = _normalize_requested_market(market_type)

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


def _stock_symbol_format_error(
    raw_symbol: object,
    symbol: str,
    market_type: str,
) -> str | None:
    if market_type == "A股" and not re.match(r"^\d{6}$", symbol):
        return f"A股代码格式错误：{raw_symbol}。Agent 已支持 600519、600519.SH、SH600519 格式。"
    if market_type == "港股" and not re.match(r"^\d{1,5}$", symbol):
        return f"港股代码格式错误：{raw_symbol}。Agent 已支持 700、0700.HK、HK09988 格式。"
    if market_type == "美股" and not re.match(r"^[A-Z]{1,5}$", symbol):
        return f"美股代码格式错误：{raw_symbol}。Agent 已支持 AAPL、TSLA、AAPL.US 格式。"
    return None


def _normalize_requested_market(raw: object) -> str | None:
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


def _normalize_symbols(
    raw_symbols: list[object],
    *,
    market_type: str | None,
    strict_symbols: bool,
) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for raw in raw_symbols:
        symbol, resolved_market = _normalize_stock_symbol_for_analysis(raw, market_type)
        error = _stock_symbol_format_error(raw, symbol, resolved_market)
        if error:
            if strict_symbols:
                raise BatchConfigError(
                    missing=["symbols"],
                    reason=error,
                    instruction="请修正股票代码格式后重试。",
                )
            skipped.append(str(raw))
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols, skipped


def _bounded_concurrency(
    raw: object,
    *,
    system_max_concurrency: int,
) -> int:
    try:
        requested = int(raw) if raw is not None else system_max_concurrency
    except (TypeError, ValueError):
        requested = system_max_concurrency
    upper_bound = max(1, system_max_concurrency)
    return max(1, min(requested, upper_bound))


def _optional_string(raw: object) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None
