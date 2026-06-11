from __future__ import annotations

from typing import Any

from app.core.database import get_postgres_db
from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple import (
    get_provider_and_url_by_model_sync,
    get_simple_analysis_service,
)
from app.services.queue.service import get_queue_service

from ..context import ToolExecutionContext
from ..permissions import BATCH_STOCK_ANALYSIS, REPORT_READ, SINGLE_STOCK_ANALYSIS
from ..registry import ResearchTool


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


def _normalize_analysts(raw: Any) -> list[str]:
    if not raw:
        return ["market", "fundamentals"]
    values = raw if isinstance(raw, list) else [raw]
    analysts: list[str] = []
    for value in values:
        key = str(value).strip()
        normalized = _ANALYST_NAME_TO_ID.get(key, key)
        if normalized in {"market", "fundamentals", "news", "social"}:
            analysts.append(normalized)
    return analysts or ["market", "fundamentals"]


def _normalize_depth(raw: Any) -> str:
    if raw is None:
        return "标准"
    return _DEPTH_TO_LABEL.get(raw, _DEPTH_TO_LABEL.get(str(raw).strip(), "标准"))


def _analysis_parameters(payload: dict[str, Any]) -> AnalysisParameters:
    return AnalysisParameters.model_validate(
        {
            "market_type": payload.get("market_type") or "A股",
            "analysis_date": payload.get("analysis_date"),
            "research_depth": _normalize_depth(payload.get("research_depth") or payload.get("depth")),
            "selected_analysts": _normalize_analysts(
                payload.get("selected_analysts") or payload.get("analysts")
            ),
            "custom_prompt": payload.get("custom_prompt"),
            "include_sentiment": bool(payload.get("include_sentiment", True)),
            "include_risk": bool(payload.get("include_risk", True)),
            "language": payload.get("language") or "zh-CN",
            "quick_analysis_model": payload.get("quick_analysis_model") or "qwen-turbo",
            "deep_analysis_model": payload.get("deep_analysis_model") or "qwen-max",
        }
    )


def _missing_model_keys(parameters: AnalysisParameters) -> list[str]:
    missing: list[str] = []
    for role_name, model_name in (
        ("快速分析模型", parameters.quick_analysis_model),
        ("深度决策模型", parameters.deep_analysis_model),
    ):
        if not model_name:
            continue
        provider_info = get_provider_and_url_by_model_sync(model_name)
        if not provider_info.get("api_key"):
            missing.append(f"{role_name} {model_name} ({provider_info.get('provider')})")
    return missing


def _queue_params(request: SingleAnalysisRequest, task_id: str, user_id: str) -> dict[str, Any]:
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


async def _single_stock_analysis(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or payload.get("stock_code") or "").strip().upper()
    if not symbol:
        return {
            "tool": "single_stock_analysis",
            "status": "config_required",
            "accepted": False,
            "missing": ["symbol"],
            "reason": "Missing required argument: symbol or stock_code.",
            "instruction": "请提供要分析的股票代码，例如 600519、000001、AAPL 或 00700。",
        }
    parameters = _analysis_parameters(payload)
    missing_keys = _missing_model_keys(parameters)
    if missing_keys:
        return {
            "tool": "single_stock_analysis",
            "status": "config_required",
            "accepted": False,
            "reason": f"模型 API Key 未配置：{'、'.join(missing_keys)}。",
            "instruction": "请先在设置中配置对应模型 API Key，或改用已配置 API Key 的模型。",
        }

    request = SingleAnalysisRequest(symbol=symbol, stock_code=symbol, parameters=parameters)
    service = get_simple_analysis_service()
    result = await service.create_analysis_task(context.principal.user_id, request)
    task_id = str(result["task_id"])

    await get_queue_service().enqueue_task(
        user_id=context.principal.user_id,
        symbol=symbol,
        params=_queue_params(request, task_id, context.principal.user_id),
        task_id=task_id,
    )

    return {
        "tool": "single_stock_analysis",
        "status": "queued",
        "accepted": True,
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
        "task_url": f"/tasks?task_id={task_id}",
        "report_url": f"/reports/view/{task_id}",
        "message": "单股分析 DAG 任务已提交到现有分析队列。",
    }


async def _batch_stock_analysis(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "batch_stock_analysis", "accepted": True, "payload": payload}


async def _stock_analysis_status(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
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
    return {
        "tool": "stock_analysis_status",
        "accepted": True,
        "task_id": task_id,
        "status": status.get("status"),
        "progress": status.get("progress", 0),
        "current_step": current_step,
        "message": status.get("message") or status.get("current_step_description"),
        "raw": status,
    }


async def _stock_analysis_report(
    context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
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
        "report_url": f"/reports/view/{task_id}",
    }


def analysis_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="single_stock_analysis",
            description=(
                "Submit the existing single-stock TradingAgents LangGraph DAG to the "
                "analysis queue. Supports market_type, analysis_date, research_depth, "
                "selected_analysts, include_sentiment/include_risk, and quick/deep models."
            ),
            permission=SINGLE_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "stock_code": {"type": "string"},
                    "market_type": {"type": "string", "enum": ["A股", "港股", "美股"]},
                    "analysis_date": {"type": "string"},
                    "research_depth": {
                        "oneOf": [
                            {"type": "string", "enum": ["快速", "基础", "标准", "深度", "全面", "1", "2", "3", "4", "5"]},
                            {"type": "number"},
                        ]
                    },
                    "selected_analysts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "analysts": {"type": "array", "items": {"type": "string"}},
                    "include_sentiment": {"type": "boolean"},
                    "include_risk": {"type": "boolean"},
                    "language": {"type": "string"},
                    "quick_analysis_model": {"type": "string"},
                    "deep_analysis_model": {"type": "string"},
                    "custom_prompt": {"type": "string"},
                },
            },
            handler=_single_stock_analysis,
        ),
        ResearchTool(
            name="stock_analysis_status",
            description="Read status/progress for an existing owner-scoped single-stock DAG task.",
            permission=SINGLE_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=_stock_analysis_status,
        ),
        ResearchTool(
            name="stock_analysis_report",
            description="Read the completed owner-scoped single-stock DAG report by task_id.",
            permission=REPORT_READ,
            schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=_stock_analysis_report,
        ),
        ResearchTool(
            name="batch_stock_analysis",
            description="Start or inspect a batch stock analysis workflow.",
            permission=BATCH_STOCK_ANALYSIS,
            schema={
                "type": "object",
                "properties": {"symbols": {"type": "array", "items": {"type": "string"}}},
                "required": ["symbols"],
            },
            handler=_batch_stock_analysis,
        ),
    ]
