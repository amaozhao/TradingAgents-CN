from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from app.core.database import get_postgres_db, get_postgres_db_sync
from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple import (
    get_provider_and_url_by_model_sync,
    get_simple_analysis_service,
)
from app.services.queue.service import get_queue_service

from .context import ToolExecutionContext
from .stage import planned_stock_stages


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

_TERMINAL_ANALYSIS_STATUSES = {"completed", "failed", "cancelled"}
_DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
_DEFAULT_POLL_INTERVAL_SECONDS = 2.0


def _stock_links(task_id: str) -> dict[str, str]:
    return {
        "task": f"/tasks?task_id={task_id}",
        "report": f"/reports/view/{task_id}",
    }


def _report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": report.get("summary", ""),
        "recommendation": report.get("recommendation", ""),
        "risk_level": report.get("risk_level"),
        "key_points": report.get("key_points", []),
    }


def _clean_model_name(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _load_active_system_config_doc() -> dict[str, Any] | None:
    db = get_postgres_db_sync()
    doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    return doc if isinstance(doc, dict) else None


def _enabled_llm_configs(doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not doc:
        return []
    configs = doc.get("llm_configs") or []
    if not isinstance(configs, list):
        return []
    return [
        config
        for config in configs
        if isinstance(config, dict)
        and config.get("model_name")
        and config.get("enabled", True) is not False
    ]


def _role_values(config: dict[str, Any]) -> set[str]:
    roles = config.get("suitable_roles") or ["both"]
    if not isinstance(roles, list):
        roles = [roles]
    return {
        str(getattr(role, "value", role)).strip().lower()
        for role in roles
        if str(getattr(role, "value", role)).strip()
    }


def _is_role_candidate(config: dict[str, Any], role: str) -> bool:
    roles = _role_values(config)
    return "both" in roles or role in roles


def _model_sort_key(config: dict[str, Any], role: str) -> tuple[int, int, float]:
    metrics = config.get("performance_metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    role_metric = metrics.get("speed" if role == "quick_analysis" else "quality", 0)
    try:
        role_score = float(role_metric or 0)
    except (TypeError, ValueError):
        role_score = 0.0
    return (
        int(config.get("priority") or 0),
        int(config.get("capability_level") or 2),
        role_score,
    )


def _provider_info_for_model(
    model_name: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if model_name not in cache:
        cache[model_name] = get_provider_and_url_by_model_sync(model_name)
    return cache[model_name]


def _model_has_configured_key(
    model_name: str, cache: dict[str, dict[str, Any]]
) -> bool:
    provider_info = _provider_info_for_model(model_name, cache)
    api_key = provider_info.get("api_key")
    return bool(str(api_key or "").strip())


def _dedupe_model_names(names: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _as_bool(raw: Any, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_positive_float(raw: Any, default: float, *, maximum: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return min(value, maximum)


def _normalize_requested_market(raw: Any) -> str | None:
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


def _normalize_stock_symbol_for_analysis(
    raw: Any, market_type: str | None
) -> tuple[str, str]:
    symbol = str(raw or "").strip().upper()
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


def _configured_model_for_role(
    *,
    doc: dict[str, Any] | None,
    role: str,
    configured_default: str | None,
    provider_cache: dict[str, dict[str, Any]],
) -> str | None:
    configs = _enabled_llm_configs(doc)
    role_candidates = sorted(
        [config for config in configs if _is_role_candidate(config, role)],
        key=lambda config: _model_sort_key(config, role),
        reverse=True,
    )
    fallback_candidates = sorted(
        configs,
        key=lambda config: _model_sort_key(config, role),
        reverse=True,
    )
    candidate_names = _dedupe_model_names(
        [configured_default]
        + [str(config["model_name"]) for config in role_candidates]
        + [str(config["model_name"]) for config in fallback_candidates]
    )
    for model_name in candidate_names:
        if _model_has_configured_key(model_name, provider_cache):
            return model_name
    return None


def _resolve_analysis_models(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    explicit_quick_model = _clean_model_name(payload.get("quick_analysis_model"))
    explicit_deep_model = _clean_model_name(payload.get("deep_analysis_model"))
    if explicit_quick_model and explicit_deep_model:
        return explicit_quick_model, explicit_deep_model

    doc = _load_active_system_config_doc()
    settings = doc.get("system_settings") if doc else {}
    if not isinstance(settings, dict):
        settings = {}
    default_model = _clean_model_name(doc.get("default_llm")) if doc else None

    provider_cache: dict[str, dict[str, Any]] = {}
    quick_model = explicit_quick_model or _configured_model_for_role(
        doc=doc,
        role="quick_analysis",
        configured_default=_clean_model_name(settings.get("quick_analysis_model"))
        or default_model,
        provider_cache=provider_cache,
    )
    deep_model = explicit_deep_model or _configured_model_for_role(
        doc=doc,
        role="deep_analysis",
        configured_default=_clean_model_name(settings.get("deep_analysis_model"))
        or default_model,
        provider_cache=provider_cache,
    )
    return quick_model, deep_model


def _normalize_analysts(
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


def _normalize_depth(raw: Any) -> str:
    if raw is None:
        return "标准"
    return _DEPTH_TO_LABEL.get(raw, _DEPTH_TO_LABEL.get(str(raw).strip(), "标准"))


def _analysis_parameters(
    payload: dict[str, Any],
) -> tuple[AnalysisParameters, list[dict[str, str]], list[dict[str, str]]]:
    quick_model, deep_model = _resolve_analysis_models(payload)
    market_type = str(payload.get("market_type") or "A股")
    analysts, skipped_stages = _normalize_analysts(
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
                "research_depth": _normalize_depth(
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


def _missing_model_keys(parameters: AnalysisParameters) -> list[str]:
    missing: list[str] = []
    for role_name, model_name in (
        ("快速分析模型", parameters.quick_analysis_model),
        ("深度决策模型", parameters.deep_analysis_model),
    ):
        if not model_name:
            missing.append(f"{role_name} 未选择可用模型")
            continue
        provider_info = get_provider_and_url_by_model_sync(model_name)
        if not provider_info.get("api_key"):
            missing.append(
                f"{role_name} {model_name} ({provider_info.get('provider')})"
            )
    return missing


def _queue_params(
    request: SingleAnalysisRequest, task_id: str, user_id: str
) -> dict[str, Any]:
    params = request.parameters.model_dump(mode="json") if request.parameters else {}
    symbol = request.get_symbol()
    params.update(
        {
            "task_id": task_id,
            "stock_code": symbol,
            "symbol": symbol,
            "user_id": user_id,
        }
    )
    return params


async def read_stock_analysis_status(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return {
            "tool": "stock_analysis_status",
            "status": "config_required",
            "accepted": False,
            "missing": ["task_id"],
            "reason": "Missing required argument: task_id.",
            "instruction": "请提供要查询的单股分析 task_id。",
        }
    status = await get_simple_analysis_service().get_task_status(
        task_id, user_id=context.principal.user_id
    )
    if not status:
        return {
            "tool": "stock_analysis_status",
            "status": "not_found",
            "accepted": False,
            "task_id": task_id,
            "reason": "未找到当前用户可访问的单股分析任务。",
        }

    current_step = (
        status.get("current_step_name")
        or status.get("current_step")
        or status.get("message")
        or status.get("status")
    )
    status_value = status.get("status")
    analysis_id = status.get("analysis_id") if status_value == "completed" else None
    return {
        "tool": "stock_analysis_status",
        "accepted": True,
        "task_id": task_id,
        "status": status_value,
        "progress": status.get("progress", 0),
        "current_step": current_step,
        "message": status.get("message") or status.get("current_step_description"),
        "analysis_id": analysis_id,
        "links": _stock_links(task_id),
        "report_url": f"/reports/view/{task_id}",
        "raw": status,
    }


async def read_stock_analysis_report(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return {
            "tool": "stock_analysis_report",
            "status": "config_required",
            "accepted": False,
            "missing": ["task_id"],
            "reason": "Missing required argument: task_id.",
            "instruction": "请提供要读取报告的单股分析 task_id。",
        }
    task_status = await get_simple_analysis_service().get_task_status(
        task_id, user_id=context.principal.user_id
    )
    if task_status:
        status_value = str(task_status.get("status") or "").lower()
        if status_value and status_value != "completed":
            return {
                "tool": "stock_analysis_report",
                "status": status_value,
                "accepted": False,
                "task_id": task_id,
                "progress": task_status.get("progress", 0),
                "current_step": (
                    task_status.get("current_step_name")
                    or task_status.get("current_step")
                    or task_status.get("message")
                    or status_value
                ),
                "reason": "单股分析任务尚未完成，不能生成或返回最终报告摘要。",
                "links": _stock_links(task_id),
                "raw_status": task_status,
            }
    db = get_postgres_db()
    report = await db.analysis_reports.find_one(
        {"task_id": task_id, "user_id": context.principal.user_id}
    )
    if not report:
        return {
            "tool": "stock_analysis_report",
            "status": "not_found",
            "accepted": False,
            "task_id": task_id,
            "reason": "分析报告尚未生成，或当前用户无权访问该报告。",
        }

    return {
        "tool": "stock_analysis_report",
        "status": report.get("status") or "completed",
        "accepted": True,
        "task_id": task_id,
        "analysis_id": report.get("analysis_id"),
        "symbol": report.get("stock_symbol") or report.get("symbol"),
        "summary": report.get("summary", ""),
        "recommendation": report.get("recommendation", ""),
        "confidence_score": report.get("confidence_score"),
        "risk_level": report.get("risk_level"),
        "key_points": report.get("key_points", []),
        "reports": report.get("reports", {}),
        "decision": report.get("decision", {}),
        "links": _stock_links(task_id),
        "report_url": f"/reports/view/{task_id}",
    }


async def _wait_for_analysis_result(
    context: ToolExecutionContext,
    *,
    service: Any,
    task_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] | None = None

    while True:
        status = await service.get_task_status(
            task_id, user_id=context.principal.user_id
        )
        if status:
            last_status = status
            status_value = str(status.get("status") or "").lower()
            if status_value == "completed":
                report = await read_stock_analysis_report(context, {"task_id": task_id})
                report_available = bool(report.get("accepted"))
                summary = _report_summary(report) if report_available else {}
                return {
                    "status": "completed",
                    "accepted": True,
                    "stage": "agent_summary",
                    "wait_status": "completed",
                    "progress": status.get("progress", 100),
                    "message": status.get("message") or "单股分析已完成。",
                    "raw_status": status,
                    "report": report if report_available else None,
                    "report_summary": summary,
                    "summary": report.get("summary", "") if report_available else "",
                    "recommendation": report.get("recommendation", "")
                    if report_available
                    else "",
                    "risk_level": report.get("risk_level")
                    if report_available
                    else None,
                    "decision": report.get("decision", {}) if report_available else {},
                }
            if status_value in _TERMINAL_ANALYSIS_STATUSES:
                error_message = (
                    status.get("error_message")
                    or status.get("last_error")
                    or status.get("error")
                    or status.get("message")
                    or f"单股分析任务已结束: {status_value}"
                )
                return {
                    "status": status_value,
                    "accepted": True,
                    "stage": "analysis_task",
                    "wait_status": status_value,
                    "progress": status.get("progress", 0),
                    "message": error_message,
                    "error_message": error_message,
                    "raw_status": status,
                }

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status_value = str((last_status or {}).get("status") or "queued").lower()
            return {
                "status": status_value,
                "accepted": True,
                "stage": "wait_bounded",
                "wait_status": "timed_out",
                "wait_timed_out": True,
                "progress": (last_status or {}).get("progress", 0),
                "message": (
                    "单股分析任务仍在执行，已返回任务链接；"
                    "如果长期停留在 pending/queued，请确认 analysis worker 进程正在运行。"
                ),
                "raw_status": last_status,
            }

        await asyncio.sleep(min(poll_interval_seconds, remaining))


class StockAnalysisWorkflow:
    def __init__(self, *, tool_name: str):
        self.tool_name = tool_name

    async def run_single(
        self, context: ToolExecutionContext, payload: dict[str, Any]
    ) -> dict[str, Any]:
        mode = str(payload.get("mode") or "single").strip().lower()
        if mode != "single":
            return {
                "tool": self.tool_name,
                "status": "config_required",
                "accepted": False,
                "reason": "stock_analysis currently supports only mode=single.",
                "instruction": "请使用 mode=single 提交单股分析。",
            }
        raw_symbol = payload.get("symbol") or payload.get("stock_code")
        symbol, market_type = _normalize_stock_symbol_for_analysis(
            raw_symbol, payload.get("market_type")
        )
        parameter_payload = {**payload, "market_type": market_type}
        parameters, skipped_stages, stage_plan = _analysis_parameters(parameter_payload)
        if not symbol:
            return {
                "tool": self.tool_name,
                "status": "config_required",
                "accepted": False,
                "missing": ["symbol"],
                "reason": "Missing required argument: symbol or stock_code.",
                "instruction": (
                    "请提供要分析的股票代码，例如 600519、000001、AAPL 或 00700。"
                ),
            }
        format_error = _stock_symbol_format_error(
            raw_symbol, symbol, parameters.market_type
        )
        if format_error:
            return {
                "tool": self.tool_name,
                "status": "config_required",
                "accepted": False,
                "reason": format_error,
                "instruction": "请提供可识别的 A 股、港股或美股代码。",
            }
        missing_keys = _missing_model_keys(parameters)
        if missing_keys:
            return {
                "tool": self.tool_name,
                "status": "config_required",
                "accepted": False,
                "reason": f"模型 API Key 未配置：{'、'.join(missing_keys)}。",
                "instruction": (
                    "请先在设置中配置对应模型 API Key，或改用已配置 API Key 的模型。"
                ),
            }

        request = SingleAnalysisRequest(
            symbol=symbol, stock_code=symbol, parameters=parameters
        )
        service = get_simple_analysis_service()
        result = await service.create_analysis_task(context.principal.user_id, request)
        task_id = str(result["task_id"])

        await get_queue_service().enqueue_task(
            user_id=context.principal.user_id,
            symbol=symbol,
            params=_queue_params(request, task_id, context.principal.user_id),
            task_id=task_id,
        )

        base_result = {
            "tool": self.tool_name,
            "mode": "single",
            "status": "queued",
            "accepted": True,
            "stage": "analysis_task",
            "wait_status": "not_waited",
            "progress": 0,
            "task_id": task_id,
            "symbol": symbol,
            "market_type": parameters.market_type,
            "analysis_date": parameters.analysis_date.isoformat()
            if parameters.analysis_date
            else None,
            "research_depth": parameters.research_depth,
            "selected_analysts": parameters.selected_analysts,
            "include_sentiment": parameters.include_sentiment,
            "include_risk": parameters.include_risk,
            "skipped_stages": skipped_stages,
            "stage_plan": stage_plan,
            "links": _stock_links(task_id),
            "task_url": f"/tasks?task_id={task_id}",
            "report_url": f"/reports/view/{task_id}",
            "message": "单股分析 DAG 任务已提交到现有分析队列。",
        }
        if not _as_bool(payload.get("wait_for_completion"), True):
            return base_result

        wait_result = await _wait_for_analysis_result(
            context,
            service=service,
            task_id=task_id,
            timeout_seconds=_as_positive_float(
                payload.get("wait_timeout_seconds"),
                _DEFAULT_WAIT_TIMEOUT_SECONDS,
                maximum=1800.0,
            ),
            poll_interval_seconds=_as_positive_float(
                payload.get("poll_interval_seconds"),
                _DEFAULT_POLL_INTERVAL_SECONDS,
                maximum=30.0,
            ),
        )
        return {**base_result, **wait_result}
