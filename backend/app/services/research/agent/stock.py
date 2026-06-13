from __future__ import annotations

import logging
import time
import uuid
from asyncio import to_thread
from datetime import datetime
from typing import Any

from app.core.database import get_postgres_db, get_postgres_db_sync
from app.schemas.analysis import AnalysisParameters
from app.services.analysis.simple import (
    create_analysis_config,
    get_provider_and_url_by_model_sync,
    get_simple_analysis_service,
)
from app.services.usage import usage_statistics_service

from .command import (
    StockAnalysisCommand,
    analysis_parameters,
    normalize_analysts,
    normalize_depth,
    normalize_requested_market,
    normalize_stock_symbol_for_analysis,
    stock_symbol_format_error,
)
from .context import ToolExecutionContext
from .emitter import StockWorkflowEventAdapter, stock_stage_progress
from .flow import StockDagParityWorkflow
from .flow.events import build_stock_workflow_stage_events
from .flow.graph import build_stock_dag_parity_plan
from .flow.stages.reports import (
    build_stock_workflow_report,
    persist_stock_workflow_report,
)
from .usage import StockUsageRecorder

logger = logging.getLogger("app.services.research.agent.stock")


def _stock_links(task_id: str) -> dict[str, str]:
    return {
        "task": f"/tasks?task_id={task_id}",
        "report": f"/reports/view/{task_id}",
    }


def _clean_model_name(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _load_active_system_config_doc() -> dict[str, Any] | None:
    try:
        db = get_postgres_db_sync()
        doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    except Exception as exc:
        logger.warning("Agent stock model config lookup failed: %s", exc)
        return None
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


def _normalize_requested_market(raw: Any) -> str | None:
    return normalize_requested_market(raw)


def _normalize_stock_symbol_for_analysis(
    raw: Any, market_type: str | None
) -> tuple[str, str]:
    return normalize_stock_symbol_for_analysis(raw, market_type)


def _stock_symbol_format_error(
    raw_symbol: Any, symbol: str, market_type: str
) -> str | None:
    return stock_symbol_format_error(raw_symbol, symbol, market_type)


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
        or default_model
        or "qwen-turbo",
        provider_cache=provider_cache,
    )
    deep_model = explicit_deep_model or _configured_model_for_role(
        doc=doc,
        role="deep_analysis",
        configured_default=_clean_model_name(settings.get("deep_analysis_model"))
        or default_model
        or "qwen-max",
        provider_cache=provider_cache,
    )
    return quick_model, deep_model


def _normalize_analysts(
    raw: Any, *, market_type: str
) -> tuple[list[str], list[dict[str, str]]]:
    return normalize_analysts(raw, market_type=market_type)


def _normalize_depth(raw: Any) -> str:
    return normalize_depth(raw)


def _analysis_parameters(
    payload: dict[str, Any],
) -> tuple[AnalysisParameters, list[dict[str, str]], list[dict[str, str]]]:
    return analysis_parameters(payload, resolve_models=_resolve_analysis_models)


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
            "instruction": "请提供要查询的个股分析 task_id。",
        }
    status = await get_simple_analysis_service().get_task_status(
        task_id, user_id=context.principal.user_id
    )
    if not status:
        try:
            status = await get_postgres_db().analysis_tasks.find_one(
                {"task_id": task_id, "user_id": context.principal.user_id}
            )
        except RuntimeError:
            status = None
        if not status:
            return {
                "tool": "stock_analysis_status",
                "status": "not_found",
                "accepted": False,
                "task_id": task_id,
                "reason": "未找到当前用户可访问的个股分析任务。",
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
            "instruction": "请提供要读取报告的个股分析 task_id。",
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
                "reason": "个股分析任务尚未完成，不能生成或返回最终报告摘要。",
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


def build_agent_stock_workflow_context(
    *,
    principal_context: ToolExecutionContext,
    symbol: str,
    market_type: str,
    parameters: AnalysisParameters,
    skipped_stages: list[dict[str, str]],
    stage_plan: list[dict[str, str]],
    task_id: str,
):
    from .flow.context import build_stock_workflow_context

    quick_model = parameters.quick_analysis_model or "qwen-turbo"
    deep_model = parameters.deep_analysis_model or quick_model
    quick_provider = _provider_info_for_model(quick_model, {})
    deep_provider = _provider_info_for_model(deep_model, {})
    config = create_analysis_config(
        parameters.research_depth,
        parameters.selected_analysts,
        quick_model,
        deep_model,
        str(quick_provider.get("provider") or "qwen"),
        market_type=market_type,
    )
    config.update(
        {
            "checkpoint_enabled": False,
            "include_sentiment": parameters.include_sentiment,
            "include_risk": parameters.include_risk,
            "skipped_stages": skipped_stages,
            "stage_plan": stage_plan,
        }
    )
    trade_date = _analysis_trade_date(parameters)
    quick_llm = _create_workflow_llm(quick_model, quick_provider)
    deep_llm = _create_workflow_llm(deep_model, deep_provider)
    return build_stock_workflow_context(
        symbol=symbol,
        trade_date=trade_date,
        asset_type="stock",
        selected_analysts=parameters.selected_analysts,
        config=config,
        quick_llm=quick_llm,
        deep_llm=deep_llm,
        attempt_id=principal_context.request_id,
        task_id=task_id,
        principal=principal_context.principal,
    )


async def run_agent_stock_workflow(
    context: ToolExecutionContext,
    *,
    tool_name: str,
    symbol: str,
    market_type: str,
    parameters: AnalysisParameters,
    skipped_stages: list[dict[str, str]],
    stage_plan: list[dict[str, str]],
    batch_id: str | None = None,
) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    workflow_context = build_agent_stock_workflow_context(
        principal_context=context,
        symbol=symbol,
        market_type=market_type,
        parameters=parameters,
        skipped_stages=skipped_stages,
        stage_plan=stage_plan,
        task_id=task_id,
    )
    await _emit_stock_workflow_stage(
        context=context,
        task_id=task_id,
        stage="validate_input",
        status="completed",
        progress=8,
        message="个股分析参数已校验。",
        batch_id=batch_id,
    )
    await _emit_stock_workflow_stage(
        context=context,
        task_id=task_id,
        stage="prepare_state",
        status="completed",
        progress=12,
        message="个股分析初始状态已准备。",
        batch_id=batch_id,
    )
    started = time.perf_counter()
    workflow_result = await to_thread(
        StockDagParityWorkflow(
            workflow_context,
            on_node_record=_stock_workflow_node_emitter(
                context=context,
                task_id=task_id,
                batch_id=batch_id,
            ),
        ).run
    )
    execution_time = time.perf_counter() - started
    report = build_stock_workflow_report(
        workflow_context,
        workflow_result.state,
        workflow_result.decision,
        execution_time=execution_time,
    )
    await persist_stock_workflow_report(workflow_context, report)
    await _record_stock_workflow_usage(
        task_id=task_id,
        symbol=symbol,
        parameters=parameters,
        report=report,
    )

    plan = build_stock_dag_parity_plan(
        parameters.selected_analysts,
        "risk_manager",
        include_risk=parameters.include_risk,
    )
    stage_events = build_stock_workflow_stage_events(
        plan=plan,
        reports=report.get("reports", {}),
        task_id=task_id,
        analysis_id=str(report.get("analysis_id") or ""),
        attempt_id=context.request_id,
    )
    links = _stock_links(task_id)
    return {
        "tool": tool_name,
        "mode": "single",
        "status": workflow_result.status,
        "accepted": workflow_result.status == "completed",
        "stage": "agent_summary",
        "wait_status": workflow_result.status,
        "progress": 100 if workflow_result.status == "completed" else 0,
        "source": workflow_result.source,
        "task_id": task_id,
        "analysis_id": report.get("analysis_id"),
        "symbol": symbol,
        "market_type": market_type,
        "analysis_date": report.get("analysis_date"),
        "research_depth": parameters.research_depth,
        "selected_analysts": parameters.selected_analysts,
        "include_sentiment": parameters.include_sentiment,
        "include_risk": parameters.include_risk,
        "skipped_stages": skipped_stages,
        "stage_plan": stage_plan,
        "node_events": list(getattr(workflow_result, "node_events", []) or []),
        "stage_events": stage_events,
        "workflow_events": list(getattr(workflow_result, "events", []) or []),
        "summary": report.get("summary", ""),
        "recommendation": report.get("recommendation", ""),
        "risk_level": report.get("risk_level"),
        "decision": report.get("decision", {}),
        "report": report,
        "links": links,
        "task_url": links["task"],
        "report_url": links["report"],
        "message": "Agent 个股分析 DAG 对齐工作流已完成。",
    }


async def _emit_stock_workflow_stage(
    *,
    context: ToolExecutionContext,
    task_id: str,
    stage: str,
    status: str,
    progress: int,
    message: str,
    batch_id: str | None = None,
) -> None:
    await StockWorkflowEventAdapter.emit_stage(
        context=context,
        task_id=task_id,
        stage=stage,
        status=status,
        progress=progress,
        message=message,
        batch_id=batch_id,
    )


def _stock_workflow_node_emitter(
    *,
    context: ToolExecutionContext,
    task_id: str,
    batch_id: str | None = None,
):
    return StockWorkflowEventAdapter.node_emitter(
        context=context,
        task_id=task_id,
        batch_id=batch_id,
    )


def _stock_stage_progress(stage: str) -> int:
    return stock_stage_progress(stage)


async def _record_stock_workflow_usage(
    *,
    task_id: str,
    symbol: str,
    parameters: AnalysisParameters,
    report: dict[str, Any],
) -> None:
    await StockUsageRecorder(
        provider_info_for_model=_provider_info_for_model,
        load_config_doc=_load_active_system_config_doc,
        enabled_llm_configs=_enabled_llm_configs,
        usage_service=usage_statistics_service,
    ).record(
        task_id=task_id,
        symbol=symbol,
        parameters=parameters,
        report=report,
    )


def _analysis_trade_date(parameters: AnalysisParameters) -> str:
    raw = parameters.analysis_date
    if raw is None:
        return datetime.now().strftime("%Y-%m-%d")
    return raw.strftime("%Y-%m-%d")


def _create_workflow_llm(model_name: str, provider_info: dict[str, Any]):
    from trader.llm.clients import create_llm_client

    provider = str(provider_info.get("provider") or "qwen")
    base_url = provider_info.get("backend_url")
    api_key = provider_info.get("api_key")
    client = create_llm_client(
        provider,
        model_name,
        base_url,
        api_key=api_key,
    )
    return client.get_llm()


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
                "instruction": "请使用 mode=single 提交个股分析。",
            }
        command = StockAnalysisCommand.from_payload(
            payload,
            resolve_models=_resolve_analysis_models,
        )
        if not command.symbol:
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
        format_error = command.symbol_format_error()
        if format_error:
            return {
                "tool": self.tool_name,
                "status": "config_required",
                "accepted": False,
                "reason": format_error,
                "instruction": "请提供可识别的 A 股、港股或美股代码。",
            }
        missing_keys = _missing_model_keys(command.parameters)
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

        return await run_agent_stock_workflow(
            context,
            tool_name=self.tool_name,
            symbol=command.symbol,
            market_type=command.parameters.market_type,
            parameters=command.parameters,
            skipped_stages=command.skipped_stages,
            stage_plan=command.stage_plan,
        )
