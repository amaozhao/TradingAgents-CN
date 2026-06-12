from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

try:
    from langchain_core.messages import BaseMessage
except Exception:  # pragma: no cover - langchain is optional for isolated tests
    BaseMessage = None  # type: ignore[assignment]

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_document
from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple.result import build_analysis_result

SOURCE = "agent_workflow_dag_parity"


class ReportRepository(Protocol):
    async def insert_report(self, document: dict[str, Any]) -> Any: ...

    async def update_task_result(self, task_id: str, result: dict[str, Any]) -> Any: ...


class PostgresReportRepository:
    async def insert_report(self, document: dict[str, Any]) -> Any:
        db = get_postgres_db()
        inserted = await db.analysis_reports.insert_one(document)
        await dual_write_hot_document("analysis_reports", document)
        return inserted

    async def update_task_result(self, task_id: str, result: dict[str, Any]) -> Any:
        document = build_stock_workflow_task_document(None, result)
        created_at = document.pop("created_at")
        db = get_postgres_db()
        updated = await db.analysis_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": document,
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
        update = {**document, "created_at": created_at}
        await dual_write_hot_document("analysis_tasks", update)
        return updated


def build_stock_workflow_report(
    context: Any,
    state: dict[str, Any],
    decision: dict[str, Any],
    *,
    execution_time: float,
) -> dict[str, Any]:
    request = SingleAnalysisRequest(
        symbol=context.symbol,
        stock_code=context.symbol,
        parameters=AnalysisParameters(
            selected_analysts=list(getattr(context, "selected_analysts", []) or []),
            research_depth=(getattr(context, "config", {}) or {}).get(
                "research_depth",
                "标准",
            ),
            include_risk=(getattr(context, "config", {}) or {}).get(
                "include_risk",
                True,
            ),
        ),
    )
    result = build_analysis_result(
        request,
        str(context.trade_date),
        state,
        decision,
        execution_time,
        task_id=getattr(context, "task_id", None),
    )
    result["source"] = SOURCE
    task_id = getattr(context, "task_id", None)
    if task_id:
        result["task_id"] = task_id
    user_id = _context_user_id(context)
    if user_id:
        result["user_id"] = user_id
    return result


async def persist_stock_workflow_report(
    context: Any,
    result: dict[str, Any],
    *,
    repository: ReportRepository | None = None,
) -> dict[str, Any]:
    task_id = str(getattr(context, "task_id", "") or result.get("task_id") or "")
    if not task_id:
        raise ValueError("task_id is required to persist stock workflow report")

    document = build_stock_workflow_report_document(context, result)
    repo = repository or PostgresReportRepository()
    await repo.insert_report(document)
    await repo.update_task_result(task_id, result)
    return document


def build_stock_workflow_report_document(
    context: Any,
    result: dict[str, Any],
    *,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    now = timestamp or datetime.now(UTC).replace(tzinfo=None)
    task_id = str(getattr(context, "task_id", "") or result.get("task_id") or "")
    user_id = _context_user_id(context) or result.get("user_id")
    document = {
        "analysis_id": result["analysis_id"],
        "stock_symbol": result.get("stock_symbol") or result.get("stock_code"),
        "stock_code": result.get("stock_code") or result.get("stock_symbol"),
        "analysis_date": result.get("analysis_date"),
        "timestamp": now,
        "status": "completed",
        "source": SOURCE,
        "summary": result.get("summary", ""),
        "analysts": result.get("analysts", []),
        "research_depth": result.get("research_depth"),
        "reports": result.get("reports", {}),
        "decision": result.get("decision", {}),
        "model_info": result.get("model_info", "Unknown"),
        "task_id": task_id,
        "recommendation": result.get("recommendation", ""),
        "confidence_score": result.get("confidence_score", 0.0),
        "risk_level": result.get("risk_level", "中等"),
        "key_points": _json_safe(result.get("key_points", [])),
        "execution_time": result.get("execution_time", 0),
        "tokens_used": result.get("tokens_used", 0),
        "performance_metrics": _json_safe(result.get("performance_metrics", {})),
        "created_at": now,
        "updated_at": now,
    }
    if user_id:
        document["user_id"] = str(user_id)
    return document


def build_stock_workflow_task_document(
    context: Any,
    result: dict[str, Any],
    *,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    now = timestamp or datetime.now(UTC).replace(tzinfo=None)
    task_id = str(
        getattr(context, "task_id", "") if context is not None else ""
    ) or str(result.get("task_id") or "")
    user_id = _context_user_id(context) if context is not None else None
    if not user_id:
        user_id = result.get("user_id")
    stock_code = result.get("stock_code") or result.get("stock_symbol")
    stock_symbol = result.get("stock_symbol") or result.get("stock_code")
    document = {
        "task_id": task_id,
        "user_id": str(user_id) if user_id else None,
        "stock_code": stock_code,
        "stock_symbol": stock_symbol,
        "analysis_id": result.get("analysis_id"),
        "status": "completed",
        "progress": 100,
        "message": "Agent 单股分析 DAG 对齐工作流已完成。",
        "current_step": "agent_summary",
        "current_step_name": "Agent 总结",
        "source": SOURCE,
        "result": _json_safe(result),
        "updated_at": now,
        "completed_at": now,
        "created_at": now,
    }
    return {key: value for key, value in document.items() if value is not None}


def write_stock_workflow_report_files(
    context: Any,
    result: dict[str, Any],
    *,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    reports = result.get("reports", {}) or {}
    files: dict[str, Path] = {}
    for report_key, filename in _REPORT_FILENAMES.items():
        content = reports.get(report_key)
        if not isinstance(content, str) or not content.strip():
            continue
        path = target / filename
        path.write_text(content.strip(), encoding="utf-8")
        files[filename] = path

    metadata = {
        "source": SOURCE,
        "task_id": getattr(context, "task_id", None) or result.get("task_id"),
        "stock_code": result.get("stock_code") or getattr(context, "symbol", None),
        "stock_symbol": result.get("stock_symbol") or getattr(context, "symbol", None),
        "analysis_date": result.get("analysis_date")
        or str(getattr(context, "trade_date", "")),
        "research_depth": result.get("research_depth"),
        "analysts": result.get("analysts", []),
        "status": "completed",
        "reports_count": len(files),
        "report_types": sorted(files),
    }
    metadata_path = target / "analysis_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    files["analysis_metadata.json"] = metadata_path
    return files


_REPORT_FILENAMES = {
    "market_report": "market_report.md",
    "sentiment_report": "sentiment_report.md",
    "news_report": "news_report.md",
    "fundamentals_report": "fundamentals_report.md",
    "investment_plan": "investment_plan.md",
    "trader_investment_plan": "trader_investment_plan.md",
    "final_trade_decision": "final_trade_decision.md",
    "research_team_decision": "research_team_decision.md",
    "risk_management_decision": "risk_management_decision.md",
}


def _context_user_id(context: Any) -> str | None:
    principal = getattr(context, "principal", None)
    user_id = getattr(principal, "user_id", None)
    if user_id is None:
        user_id = getattr(context, "user_id", None)
    return str(user_id) if user_id else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if BaseMessage is not None and isinstance(value, BaseMessage):
        return _message_to_json(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(mode="json"))
        except TypeError:
            return _json_safe(value.model_dump())
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _message_to_json(message: Any) -> dict[str, Any]:
    fields = {
        "type": getattr(message, "type", message.__class__.__name__),
        "content": getattr(message, "content", ""),
        "id": getattr(message, "id", None),
        "name": getattr(message, "name", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
        "response_metadata": getattr(message, "response_metadata", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "invalid_tool_calls": getattr(message, "invalid_tool_calls", None),
        "tool_call_id": getattr(message, "tool_call_id", None),
    }
    return {
        key: _json_safe(item)
        for key, item in fields.items()
        if item not in (None, {}, [])
    }
