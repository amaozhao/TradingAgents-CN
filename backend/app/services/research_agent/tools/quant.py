from __future__ import annotations

import math
from typing import Any

from app.services.research_agent.artifacts import ResearchArtifactService

from ..context import ToolExecutionContext
from ..permissions import BACKTEST_RUN, FACTOR_RUN, OPTIONS_RUN, PATTERN_RUN
from ..registry import ResearchTool


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


async def _options_pricing(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    spot = float(payload.get("spot"))
    strike = float(payload.get("strike"))
    rate = float(payload.get("rate") or 0.0)
    volatility = float(payload.get("volatility"))
    time_to_expiry = float(payload.get("time_to_expiry") or payload.get("years") or 0.0)
    option_type = str(payload.get("option_type") or "call").lower()
    if spot <= 0 or strike <= 0 or volatility <= 0 or time_to_expiry <= 0:
        raise ValueError("spot, strike, volatility, and time_to_expiry must be positive")
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be call or put")
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
    if not returns:
        return {
            "tool": "backtest",
            "status": "config_required",
            "accepted": False,
            "reason": "returns or prices are required; the agent will not fabricate backtest data.",
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
            schema={"type": "object", "additionalProperties": True},
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
            description="Run a research-only backtest from caller-provided returns/prices and optional signals.",
            permission=BACKTEST_RUN,
            schema={"type": "object", "additionalProperties": True},
            handler=_backtest,
        ),
    ]
