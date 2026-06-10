from __future__ import annotations

import math
from typing import Any

from app.services.research.agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import BACKTEST_RUN, FACTOR_RUN, OPTIONS_RUN, PATTERN_RUN
from ..registry import ResearchTool
from .market.series import build_returns_frame, load_price_series, normalize_symbols, summarize_returns


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _config_required(reason: str) -> dict[str, Any]:
    return {
        "tool": "options_pricing",
        "status": "config_required",
        "accepted": False,
        "reason": reason,
    }


def _positive_float(payload: dict[str, Any], field: str) -> tuple[float | None, str | None]:
    value = payload.get(field)
    if value is None or value == "":
        return None, field
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, field
    if number <= 0:
        return None, field
    return number, None


async def _options_pricing(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    missing_or_invalid: list[str] = []
    spot, invalid = _positive_float(payload, "spot")
    if invalid:
        missing_or_invalid.append(invalid)
    strike, invalid = _positive_float(payload, "strike")
    if invalid:
        missing_or_invalid.append(invalid)
    volatility, invalid = _positive_float(payload, "volatility")
    if invalid:
        missing_or_invalid.append(invalid)
    time_field = "time_to_expiry" if payload.get("time_to_expiry") is not None else "years"
    time_to_expiry, invalid = _positive_float(payload, time_field)
    if invalid:
        missing_or_invalid.append("time_to_expiry")
    if missing_or_invalid:
        fields = ", ".join(missing_or_invalid)
        return _config_required(
            f"{fields} must be provided as positive numeric inputs; the agent will not fabricate option pricing inputs."
        )
    try:
        rate = float(payload.get("rate") or 0.0)
    except (TypeError, ValueError):
        return _config_required("rate must be numeric when provided")
    option_type = str(payload.get("option_type") or "call").lower()
    if option_type not in {"call", "put"}:
        return _config_required("option_type must be call or put")
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility * volatility) * time_to_expiry) / (
        volatility * math.sqrt(time_to_expiry)
    )
    d2 = d1 - volatility * math.sqrt(time_to_expiry)
    discount = math.exp(-rate * time_to_expiry)
    if option_type == "call":
        price = spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
        delta = _norm_cdf(d1)
    else:
        price = strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
    gamma = math.exp(-0.5 * d1 * d1) / (spot * volatility * math.sqrt(2 * math.pi * time_to_expiry))
    return {
        "tool": "options_pricing",
        "status": "completed",
        "model": "black_scholes",
        "inputs": {
            "spot": spot,
            "strike": strike,
            "rate": rate,
            "volatility": volatility,
            "time_to_expiry": time_to_expiry,
            "option_type": option_type,
        },
        "price": price,
        "greeks": {"delta": delta, "gamma": gamma},
    }


def _numbers(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    out = []
    for value in values:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def _symbol_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in (
            "symbols",
            "codes",
            "tickers",
            "assets",
            "instruments",
            "items",
            "item",
            "value",
        ):
            if key in value:
                return _symbol_values(value.get(key))
        for key in ("symbol", "code", "ticker", "asset"):
            if key in value:
                return [value.get(key)]
        return []
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_symbol_values(item) if isinstance(item, dict) else [item])
        return out
    return [value]


def _symbols_from_payload(payload: dict[str, Any]) -> list[str]:
    for key in (
        "symbols",
        "codes",
        "tickers",
        "assets",
        "instruments",
        "universe",
        "portfolio_symbols",
        "portfolio",
        "asset_universe",
    ):
        symbols = normalize_symbols(_symbol_values(payload.get(key)))
        if symbols:
            return symbols
    return []


async def _pattern(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    prices = _numbers(payload.get("prices") or payload.get("close"))
    if len(prices) < 3:
        return {
            "tool": "pattern",
            "status": "config_required",
            "accepted": False,
            "reason": "At least three numeric prices are required; the agent will not fabricate pattern data.",
        }
    first = prices[0]
    last = prices[-1]
    high = max(prices)
    low = min(prices)
    changes = [prices[index] - prices[index - 1] for index in range(1, len(prices))]
    up_moves = len([change for change in changes if change > 0])
    down_moves = len([change for change in changes if change < 0])
    trend = "uptrend" if last > first and up_moves >= down_moves else "downtrend" if last < first and down_moves >= up_moves else "range"
    breakout = last >= high and high > first
    breakdown = last <= low and low < first
    return {
        "tool": "pattern",
        "status": "completed",
        "pattern": {
            "trend": trend,
            "breakout": breakout,
            "breakdown": breakdown,
            "observations": len(prices),
            "first": first,
            "last": last,
            "high": high,
            "low": low,
        },
    }


async def _factor_analysis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    prices = _numbers(payload.get("prices") or payload.get("close"))
    returns = _numbers(payload.get("returns"))
    if not returns and len(prices) >= 2:
        returns = [(prices[index] / prices[index - 1]) - 1 for index in range(1, len(prices)) if prices[index - 1] != 0]
    if not returns:
        return {
            "tool": "factor_analysis",
            "status": "config_required",
            "accepted": False,
            "reason": "prices or returns are required; the agent will not fabricate factor inputs.",
        }
    momentum = sum(returns)
    mean = momentum / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    metrics = {
        "observations": len(returns),
        "momentum": momentum,
        "mean_return": mean,
        "volatility": math.sqrt(variance),
        "positive_rate": len([value for value in returns if value > 0]) / len(returns),
    }
    artifact = None
    if context.session_id:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            artifact_type="factor_analysis",
            payload={"metrics": metrics, "factor": payload.get("factor") or "custom"},
        )
    return {
        "tool": "factor_analysis",
        "status": "completed",
        "metrics": metrics,
        "artifact_id": artifact.get("artifact_id") if artifact else None,
    }


async def _backtest(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    returns = _numbers(payload.get("returns"))
    signals = _numbers(payload.get("signals"))
    prices = _numbers(payload.get("prices") or payload.get("close"))
    if not returns and len(prices) >= 2:
        returns = [(prices[index] / prices[index - 1]) - 1 for index in range(1, len(prices)) if prices[index - 1] != 0]
    symbols = _symbols_from_payload(payload)
    if not returns and symbols:
        series_map = await load_price_series(
            symbols,
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            limit=int(payload.get("limit") or 252),
        )
        returns_frame = build_returns_frame(series_map)
        if not returns_frame.empty:
            returns_frame = returns_frame.fillna(0.0)
            vol = returns_frame.std().replace(0, float("nan"))
            inv_vol = (1 / vol).dropna()
            if inv_vol.empty:
                weights = {column: round(1 / len(returns_frame.columns), 6) for column in returns_frame.columns}
            else:
                total_inv = float(inv_vol.sum())
                weights = {column: round(float(inv_vol[column] / total_inv), 6) for column in inv_vol.index}
                for column in returns_frame.columns:
                    weights.setdefault(column, 0.0)
            portfolio = returns_frame.mul(weights).sum(axis=1)
            returns = [float(value) for value in portfolio.to_list()]
            missing_symbols = [
                symbol for symbol, data in series_map.items()
                if not data.get("returns")
            ]
            metrics = summarize_returns(returns)
            artifact = None
            if context.session_id:
                artifact = await ResearchArtifactService().create_artifact(
                    session_id=str(context.session_id),
                    user_id=context.principal.user_id,
                    artifact_type="backtest_run",
                    payload={
                        "run_id": payload.get("run_id"),
                        "strategy": payload.get("strategy") or payload.get("optimizer") or "risk_parity",
                        "symbols": symbols,
                        "weights": weights,
                        "metrics": metrics,
                        "series_sources": {
                            symbol: data.get("source") for symbol, data in series_map.items()
                        },
                        "missing_symbols": missing_symbols,
                        "research_only": True,
                    },
                )
            return {
                "tool": "backtest",
                "status": "completed" if metrics.get("observations") else "degraded",
                "strategy": payload.get("strategy") or payload.get("optimizer") or "risk_parity",
                "symbols": symbols,
                "weights": weights,
                "metrics": metrics,
                "series_sources": {
                    symbol: data.get("source") for symbol, data in series_map.items()
                },
                "missing_symbols": missing_symbols,
                "data_limitations": [
                    "Research-only backtest; not investment advice.",
                    "Weights use inverse-volatility risk-parity approximation.",
                    "Symbols with unavailable data are excluded and listed in missing_symbols.",
                ],
                "artifact_id": artifact.get("artifact_id") if artifact else None,
            }
    if not returns:
        return {
            "tool": "backtest",
            "status": "config_required",
            "accepted": False,
            "reason": "returns, prices, or symbols with fetchable market data are required; the agent will not fabricate backtest data.",
        }
    if signals and len(signals) < len(returns):
        signals = [*signals, *([signals[-1]] * (len(returns) - len(signals)))]
    strategy_returns = [
        value * (signals[index] if signals else 1.0)
        for index, value in enumerate(returns)
    ]
    equity = 1.0
    curve = []
    peak = 1.0
    max_drawdown = 0.0
    for value in strategy_returns:
        equity *= 1 + value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
        curve.append(equity)
    total_return = equity - 1
    mean = sum(strategy_returns) / len(strategy_returns)
    variance = sum((value - mean) ** 2 for value in strategy_returns) / len(strategy_returns)
    volatility = math.sqrt(variance)
    metrics = {
        "observations": len(strategy_returns),
        "total_return": total_return,
        "mean_return": mean,
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "win_rate": len([value for value in strategy_returns if value > 0]) / len(strategy_returns),
    }
    artifact = None
    if context.session_id:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            artifact_type="backtest_run",
            payload={
                "run_id": payload.get("run_id"),
                "metrics": metrics,
                "equity_curve": curve,
                "research_only": True,
            },
        )
    return {
        "tool": "backtest",
        "status": "completed",
        "metrics": metrics,
        "equity_curve": curve,
        "artifact_id": artifact.get("artifact_id") if artifact else None,
    }


def quant_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="options_pricing",
            description="Price call/put options with Black-Scholes from caller-provided inputs.",
            permission=OPTIONS_RUN,
            schema={
                "type": "object",
                "properties": {
                    "spot": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Current underlying price.",
                    },
                    "strike": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Option strike price.",
                    },
                    "volatility": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Annualized volatility as a decimal, for example 0.2 for 20%.",
                    },
                    "time_to_expiry": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Years to expiry, for example 0.5 for six months.",
                    },
                    "years": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "description": "Alias for time_to_expiry.",
                    },
                    "rate": {
                        "type": "number",
                        "description": "Optional annual risk-free rate as a decimal.",
                    },
                    "option_type": {
                        "type": "string",
                        "enum": ["call", "put"],
                        "description": "Option side.",
                    },
                },
                "required": ["spot", "strike", "volatility", "time_to_expiry"],
                "additionalProperties": True,
            },
            handler=_options_pricing,
        ),
        ResearchTool(
            name="pattern",
            description="Detect simple trend/breakout patterns from caller-provided price series.",
            permission=PATTERN_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_pattern,
        ),
        ResearchTool(
            name="factor_analysis",
            description="Compute simple factor diagnostics from caller-provided prices or returns.",
            permission=FACTOR_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_factor_analysis,
        ),
        ResearchTool(
            name="backtest",
            description=(
                "Run a research-only backtest from caller-provided returns/prices or directly from "
                "symbols/start_date/end_date. When symbols are provided, free/current-project data "
                "sources are used and a risk-parity style inverse-volatility portfolio is computed."
            ),
            permission=BACKTEST_RUN,
            schema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ticker list, for example ['000001.SZ','BTC-USDT','AAPL'].",
                    },
                    "codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alias for symbols.",
                    },
                    "returns": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Caller-provided return series if market data is not needed.",
                    },
                    "prices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Caller-provided close price series.",
                    },
                    "signals": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Optional position signal series multiplied by returns.",
                    },
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "strategy": {
                        "type": "string",
                        "description": "Strategy label, for example risk_parity.",
                    },
                    "optimizer": {
                        "type": "string",
                        "description": "Portfolio optimizer label, for example risk_parity.",
                    },
                    "limit": {"type": "integer"},
                },
                "additionalProperties": True,
            },
            handler=_backtest,
        ),
    ]
