from __future__ import annotations

from typing import Any

from sqlalchemy import Select, desc, select

from app.db.model import AnalysisReport, AnalysisTask


def build_analysis_task_by_task_id_select(task_id: str) -> Select:
    return select(AnalysisTask).where(AnalysisTask.task_id == task_id)


def build_analysis_report_by_task_id_select(task_id: str) -> Select:
    return select(AnalysisReport).where(AnalysisReport.task_id == task_id)


def build_analysis_report_by_analysis_id_select(analysis_id: str) -> Select:
    return select(AnalysisReport).where(AnalysisReport.analysis_id == analysis_id)


def build_user_analysis_tasks_select(
    user_id: str,
    *,
    status: str | None = None,
    limit: int,
    offset: int = 0,
) -> Select:
    statement = select(AnalysisTask).where(AnalysisTask.user_id == user_id)
    if status:
        statement = statement.where(AnalysisTask.status == status)
    return statement.order_by(desc(AnalysisTask.created_at)).offset(offset).limit(limit)


async def get_analysis_task_by_task_id(session, task_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_analysis_task_by_task_id_select(task_id))
    row = result.scalars().first()
    return _task_to_dict(row) if row else None


async def get_analysis_report_by_task_id(session, task_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_analysis_report_by_task_id_select(task_id))
    row = result.scalars().first()
    return _report_to_dict(row) if row else None


async def get_analysis_report_by_analysis_id(session, analysis_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_analysis_report_by_analysis_id_select(analysis_id))
    row = result.scalars().first()
    return _report_to_dict(row) if row else None


async def list_user_analysis_tasks(
    session,
    user_id: str,
    *,
    status: str | None = None,
    limit: int,
    offset: int = 0,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_user_analysis_tasks_select(user_id, status=status, limit=limit, offset=offset)
    )
    return [_task_to_dict(row) for row in result.scalars()]


def _task_to_dict(row: AnalysisTask) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "legacy_id": row.legacy_id,
        "task_id": row.task_id,
        "user_id": row.user_id,
        "stock_symbol": row.stock_symbol,
        "symbol": payload.get("symbol") or row.stock_symbol,
        "stock_code": payload.get("stock_code") or row.stock_symbol,
        "status": row.status,
        "progress": row.progress,
        "created_at": payload.get("created_at") or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at") or (row.updated_at.isoformat() if row.updated_at else None),
    }
    data.pop("_id", None)
    return {key: value for key, value in data.items() if value is not None}


def _report_to_dict(row: AnalysisReport) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "legacy_id": row.legacy_id,
        "analysis_id": row.analysis_id,
        "task_id": row.task_id or payload.get("task_id"),
        "user_id": row.user_id,
        "stock_symbol": row.stock_symbol,
        "analysis_date": payload.get("analysis_date") or (row.analysis_date.isoformat() if row.analysis_date else None),
        "summary": row.summary,
        "created_at": payload.get("created_at") or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at") or (row.updated_at.isoformat() if row.updated_at else None),
    }
    data.pop("_id", None)
    return {key: value for key, value in data.items() if value is not None}
