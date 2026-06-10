from __future__ import annotations

import asyncio
import math
import socket
import threading
import time
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

import pandas as pd

from app.core.baostock.runtime import baostock_session
from app.core.network.proxy import ensure_cn_market_no_proxy
from app.services.research.agent.artifacts import ResearchArtifactService

from ...context import ToolExecutionContext
from ...permissions import BACKTEST_RUN
from ...registry import ResearchTool


T = TypeVar("T")

FACTOR_ALIASES = {
    "momentum": "momentum",
    "reversal": "reversal",
    "volatility": "volatility",
    "turnover": "turnover",
}


async def _run_in_daemon_thread(
    func: Callable[..., T],
    *args: Any,
    timeout: float,
    **kwargs: Any,
) -> T:
    """Run blocking market-data work without touching asyncio's default executor."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T] = loop.create_future()

    def finish_with_result(result: T) -> None:
        if not future.done():
            future.set_result(result)

    def finish_with_exception(exc: BaseException) -> None:
        if not future.done():
            future.set_exception(exc)

    def worker() -> None:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            try:
                loop.call_soon_threadsafe(finish_with_exception, exc)
            except RuntimeError:
                pass
            return
        try:
            loop.call_soon_threadsafe(finish_with_result, result)
        except RuntimeError:
            pass

    thread = threading.Thread(
        target=worker,
        name="research-agent-multi-factor",
        daemon=True,
    )
    thread.start()
    return await asyncio.wait_for(future, timeout=timeout)


def _normalize_cn_symbol(code: str) -> str:
    raw = str(code).strip().upper()
    if raw.startswith(("SH.", "SZ.")):
        return raw.lower()
    raw = raw.removesuffix(".SH").removesuffix(".SZ")
    prefix = "sh" if raw.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}.{raw}"


def _plain_symbol(baostock_symbol: str) -> str:
    return baostock_symbol.split(".", 1)[1] if "." in baostock_symbol else baostock_symbol


def _zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1, skipna=True)
    std = frame.std(axis=1, skipna=True).replace(0, pd.NA)
    return frame.sub(mean, axis=0).div(std, axis=0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _performance_metrics(returns: pd.Series) -> dict[str, float | int]:
    clean = returns.dropna()
    if clean.empty:
        return {
            "observations": 0,
            "total_return": 0.0,
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
        }

    equity = (1 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1
    total_return = float(equity.iloc[-1] - 1)
    annualized_return = float((1 + total_return) ** (252 / len(clean)) - 1)
    volatility = float(clean.std(ddof=1) * math.sqrt(252)) if len(clean) > 1 else 0.0
    sharpe = float(annualized_return / volatility) if volatility else 0.0
    return {
        "observations": int(len(clean)),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((clean > 0).mean()),
    }


def _compute_factor_model(
    close: pd.DataFrame,
    turnover: pd.DataFrame,
    *,
    requested_factors: list[str],
) -> dict[str, Any]:
    returns = close.pct_change()
    next_returns = returns.shift(-1)
    raw_factors: dict[str, pd.DataFrame] = {
        "momentum": close.pct_change(20),
        "reversal": -close.pct_change(5),
        "volatility": -returns.rolling(20, min_periods=20).std(),
        "turnover": turnover.rolling(20, min_periods=20).mean(),
    }
    factors = {
        name: _zscore(raw_factors[name])
        for name in requested_factors
        if name in raw_factors
    }
    ic_by_factor: dict[str, pd.Series] = {}
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="An input array is constant; the correlation coefficient is not defined.",
        )
        for name, factor in factors.items():
            ic_by_factor[name] = factor.corrwith(next_returns, axis=1, method="spearman")

    mean_ic = {
        name: _safe_float(series.dropna().mean())
        for name, series in ic_by_factor.items()
    }
    denominator = sum(abs(value) for value in mean_ic.values())
    if denominator <= 0:
        weights = {name: round(1 / len(factors), 6) for name in factors} if factors else {}
    else:
        weights = {
            name: round(value / denominator, 6)
            for name, value in mean_ic.items()
        }

    composite = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for name, factor in factors.items():
        composite = composite.add(factor.fillna(0.0) * weights.get(name, 0.0), fill_value=0.0)

    long_short_returns: list[float] = []
    long_only_returns: list[float] = []
    for date in composite.index[:-1]:
        scores = composite.loc[date].dropna()
        future = next_returns.loc[date].dropna()
        aligned = scores.index.intersection(future.index)
        if len(aligned) < 5:
            long_short_returns.append(float("nan"))
            long_only_returns.append(float("nan"))
            continue
        scores = scores.loc[aligned].sort_values()
        bucket = max(1, int(len(scores) * 0.2))
        short_symbols = scores.index[:bucket]
        long_symbols = scores.index[-bucket:]
        long_ret = future.loc[long_symbols].mean()
        short_ret = future.loc[short_symbols].mean()
        long_short_returns.append(float(long_ret - short_ret))
        long_only_returns.append(float(long_ret))

    result_index = composite.index[:-1]
    long_short = pd.Series(long_short_returns, index=result_index)
    long_only = pd.Series(long_only_returns, index=result_index)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="An input array is constant; the correlation coefficient is not defined.",
        )
        composite_ic = composite.corrwith(next_returns, axis=1, method="spearman")

    return {
        "weights": weights,
        "factor_ic": {
            name: {
                "mean_ic": mean_ic[name],
                "positive_rate": _safe_float((series.dropna() > 0).mean()),
                "observations": int(series.dropna().shape[0]),
            }
            for name, series in ic_by_factor.items()
        },
        "composite_ic": {
            "mean_ic": _safe_float(composite_ic.dropna().mean()),
            "positive_rate": _safe_float((composite_ic.dropna() > 0).mean()),
            "observations": int(composite_ic.dropna().shape[0]),
        },
        "long_short_returns": long_short,
        "long_only_returns": long_only,
    }


def _load_hs300_constituents(limit: int) -> tuple[list[str], int, str]:
    ensure_cn_market_no_proxy()
    import akshare as ak

    df = ak.index_stock_cons(symbol="000300")
    code_column = "品种代码" if "品种代码" in df.columns else "成分券代码"
    codes = [str(value).zfill(6) for value in df[code_column].dropna().tolist()]
    return codes[:limit], len(codes), "akshare.index_stock_cons"


def _load_baostock_history(
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    max_runtime_seconds: float = 180.0,
    min_success_before_break: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    started_at = time.monotonic()
    previous_socket_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(12)
    close_frames: list[pd.Series] = []
    turnover_frames: list[pd.Series] = []
    diagnostics: dict[str, str] = {}
    consecutive_failures = 0
    try:
        with baostock_session() as bs:

            def relogin() -> None:
                try:
                    bs.logout()
                except Exception:
                    pass
                time.sleep(0.2)
                lg = bs.login()
                if lg.error_code != "0":
                    raise RuntimeError(f"baostock login failed: {lg.error_msg}")

            for code in symbols:
                elapsed = time.monotonic() - started_at
                if elapsed > max_runtime_seconds:
                    suffix = (
                        f"; loaded {len(close_frames)} of {len(symbols)} requested symbols"
                        if len(close_frames) >= min_success_before_break
                        else f"; only loaded {len(close_frames)} of {len(symbols)} requested symbols"
                    )
                    diagnostics["_truncated"] = (
                        f"baostock runtime budget exceeded after {elapsed:.1f}s{suffix}"
                    )
                    break
                if consecutive_failures >= 20:
                    diagnostics["_truncated"] = (
                        f"baostock stopped after {consecutive_failures} consecutive failures; "
                        f"loaded {len(close_frames)} of {len(symbols)} requested symbols"
                    )
                    break

                bs_code = _normalize_cn_symbol(code)
                symbol = _plain_symbol(bs_code)
                rows = []
                fields: list[str] = []
                last_error = ""
                for attempt in range(2):
                    try:
                        rs = bs.query_history_k_data_plus(
                            bs_code,
                            "date,code,close,turn",
                            start_date=start_date,
                            end_date=end_date,
                            frequency="d",
                            adjustflag="2",
                        )
                        if rs.error_code != "0":
                            last_error = rs.error_msg
                            break
                        fields = list(rs.fields)
                        while rs.next():
                            rows.append(rs.get_row_data())
                        break
                    except Exception as exc:
                        last_error = f"{exc.__class__.__name__}: {exc}"
                        if attempt == 0:
                            relogin()
                            continue
                time.sleep(0.05)
                if last_error:
                    diagnostics[symbol] = last_error
                    consecutive_failures += 1
                    continue
                if not rows:
                    diagnostics[symbol] = "no rows"
                    consecutive_failures += 1
                    continue
                df = pd.DataFrame(rows, columns=fields)
                df["date"] = pd.to_datetime(df["date"])
                close_frames.append(
                    pd.to_numeric(df["close"], errors="coerce")
                    .rename(symbol)
                    .set_axis(df["date"])
                )
                turnover_frames.append(
                    pd.to_numeric(df["turn"], errors="coerce")
                    .rename(symbol)
                    .set_axis(df["date"])
                )
                consecutive_failures = 0
    finally:
        socket.setdefaulttimeout(previous_socket_timeout)

    close = pd.concat(close_frames, axis=1).sort_index() if close_frames else pd.DataFrame()
    turnover = pd.concat(turnover_frames, axis=1).sort_index() if turnover_frames else pd.DataFrame()
    return close, turnover, diagnostics


def _build_multi_factor_alpha_result(payload: dict[str, Any]) -> dict[str, Any]:
    universe = str(payload.get("universe") or "hs300").lower()
    if universe not in {"hs300", "沪深300", "csi300", "000300"}:
        return {
            "tool": "multi_factor_alpha_backtest",
            "status": "config_required",
            "accepted": False,
            "reason": "Only hs300/csi300 universe is currently supported by the local free-data implementation.",
        }

    requested_factors = [
        FACTOR_ALIASES[str(item).lower()]
        for item in (payload.get("factors") or ["momentum", "reversal", "volatility", "turnover"])
        if str(item).lower() in FACTOR_ALIASES
    ]
    if not requested_factors:
        requested_factors = ["momentum", "reversal", "volatility", "turnover"]

    start_date = str(payload.get("start_date") or "2023-01-01")
    end_date = str(payload.get("end_date") or "2024-12-31")
    requested_sample_size = payload.get("sample_size") or payload.get("limit") or 60
    sample_size = max(10, min(int(requested_sample_size), 300))

    constituents, universe_count, universe_source = _load_hs300_constituents(sample_size)
    try:
        close, turnover, diagnostics = _load_baostock_history(
            constituents,
            start_date=start_date,
            end_date=end_date,
            max_runtime_seconds=float(payload.get("max_runtime_seconds") or 180),
        )
    except Exception as exc:
        return {
            "tool": "multi_factor_alpha_backtest",
            "status": "degraded",
            "accepted": False,
            "reason": "BaoStock history source is unavailable, so the multi-factor backtest could not load enough price series.",
            "universe_count": universe_count,
            "sampled_count": len(constituents),
            "loaded_symbols": 0,
            "source_diagnostics": {"history": str(exc)},
            "data_limitations": [
                "Free-data research backtest; not investment advice.",
                "BaoStock login/query can fail due to upstream network availability.",
            ],
        }
    if close.empty or close.shape[1] < 5:
        return {
            "tool": "multi_factor_alpha_backtest",
            "status": "degraded",
            "accepted": False,
            "reason": "BaoStock did not return enough HS300 constituent price series for factor backtest.",
            "universe_count": universe_count,
            "sampled_count": len(constituents),
            "loaded_symbols": int(close.shape[1]),
            "source_diagnostics": diagnostics,
        }

    model = _compute_factor_model(close, turnover, requested_factors=requested_factors)
    metrics = {
        "long_short": _performance_metrics(model["long_short_returns"]),
        "long_only_top_quantile": _performance_metrics(model["long_only_returns"]),
    }
    artifact_payload = {
        "universe": "hs300",
        "universe_count": universe_count,
        "sampled_symbols": list(close.columns),
        "requested_factors": requested_factors,
        "start_date": start_date,
        "end_date": end_date,
        "ic_weights": model["weights"],
        "factor_ic": model["factor_ic"],
        "composite_ic": model["composite_ic"],
        "metrics": metrics,
        "data_source": {
            "universe": universe_source,
            "history": "baostock.query_history_k_data_plus",
        },
        "source_diagnostics": diagnostics,
        "research_only": True,
    }
    result = {
        "tool": "multi_factor_alpha_backtest",
        "status": "completed",
        "universe": "hs300",
        "universe_count": universe_count,
        "sampled_count": int(close.shape[1]),
        "start_date": start_date,
        "end_date": end_date,
        "factors": requested_factors,
        "ic_weights": model["weights"],
        "factor_ic": model["factor_ic"],
        "composite_ic": model["composite_ic"],
        "metrics": metrics,
        "data_source": {
            "universe": universe_source,
            "history": "baostock.query_history_k_data_plus",
        },
        "data_limitations": [
            "Free-data research backtest; not investment advice.",
            "HS300 membership is current AKShare membership, not point-in-time historical membership.",
            "Interactive free-data run defaults to a bounded sample because BaoStock can hang or reset on full 300-symbol batches; use a cached batch job for full-universe production research.",
            "Factors use daily close/turnover approximations: momentum=20D return, reversal=-5D return, volatility=-20D return std, turnover=20D average turnover.",
        ],
        "source_diagnostics": diagnostics,
        "artifact_id": None,
        "_artifact_payload": artifact_payload,
    }
    return result


async def _multi_factor_alpha_backtest(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    timeout = float(payload.get("max_runtime_seconds") or 180) + 30.0
    try:
        result = await _run_in_daemon_thread(
            _build_multi_factor_alpha_result,
            payload,
            timeout=timeout,
        )
    except TimeoutError:
        result = {
            "tool": "multi_factor_alpha_backtest",
            "status": "degraded",
            "accepted": False,
            "reason": "Multi-factor backtest exceeded its runtime budget before enough market data could be loaded.",
            "source_diagnostics": {"runtime": f"timed out after {timeout:.1f}s"},
        }
    artifact_payload = result.pop("_artifact_payload", None)
    if context.session_id and artifact_payload:
        artifact = await ResearchArtifactService().create_artifact(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            artifact_type="multi_factor_alpha_backtest",
            payload=artifact_payload,
        )
        result["artifact_id"] = artifact.get("artifact_id")
    return result


def multi_factor_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="multi_factor_alpha_backtest",
            description=(
                "Build and backtest a HS300 multi-factor alpha model with momentum, reversal, "
                "volatility, and turnover using IC-weighted composite signals. This is an "
                "interactive free-data run with a bounded sample by default because BaoStock can "
                "hang/reset on full 300-symbol batches. Use this tool for requests asking for "
                "沪深300/CSI300 multi-factor IC weighting and 2023-2024 backtests, and state the "
                "sampled_count/data limitations in the answer."
            ),
            permission=BACKTEST_RUN,
            schema={
                "type": "object",
                "properties": {
                    "universe": {"type": "string", "description": "hs300/csi300/沪深300"},
                    "factors": {"type": "array", "items": {"type": "string"}},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "sample_size": {"type": "integer", "description": "10-300; default 60 for interactive stability"},
                    "use_sample": {
                        "type": "boolean",
                        "description": "Deprecated; interactive runs are sampled unless the caller explicitly raises sample_size.",
                    },
                },
                "additionalProperties": True,
            },
            handler=_multi_factor_alpha_backtest,
        )
    ]
