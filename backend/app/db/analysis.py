from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Select, desc, func, or_, select

from app.models.table import AnalysisReport, AnalysisTask


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
    batch_id: str | None = None,
    limit: int,
    offset: int = 0,
) -> Select:
    statement = select(AnalysisTask).where(AnalysisTask.user_id == user_id)
    if status:
        statement = statement.where(AnalysisTask.status == status)
    if batch_id:
        statement = statement.where(
            AnalysisTask.payload["batch_id"].as_string() == batch_id
        )
    return statement.order_by(desc(AnalysisTask.created_at)).offset(offset).limit(limit)


def build_user_analysis_reports_page_select(
    *,
    user_id: str | None,
    is_admin: bool,
    keyword: str | None,
    market: str | None,
    stock_code: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int,
    offset: int = 0,
) -> Select:
    statement = select(
        AnalysisReport.analysis_id.label("id"),
        AnalysisReport.analysis_id,
        AnalysisReport.task_id,
        AnalysisReport.user_id,
        AnalysisReport.stock_symbol,
        AnalysisReport.analysis_date,
        AnalysisReport.summary,
        AnalysisReport.created_at,
        AnalysisReport.payload["stock_name"].astext.label("stock_name"),
        AnalysisReport.payload["market_type"].astext.label("market_type"),
        AnalysisReport.payload["model_info"].astext.label("model_info"),
        AnalysisReport.payload["status"].astext.label("status"),
        AnalysisReport.payload["analysts"].label("analysts"),
        AnalysisReport.payload["research_depth"].astext.label("research_depth"),
        AnalysisReport.payload["source"].astext.label("source"),
    ).where(
        *_report_filters(
            user_id, is_admin, keyword, market, stock_code, start_date, end_date
        )
    )
    return (
        statement.order_by(desc(AnalysisReport.created_at)).offset(offset).limit(limit)
    )


def build_user_analysis_reports_count_select(
    *,
    user_id: str | None,
    is_admin: bool,
    keyword: str | None,
    market: str | None,
    stock_code: str | None,
    start_date: str | None,
    end_date: str | None,
) -> Select:
    return (
        select(func.count())
        .select_from(AnalysisReport)
        .where(
            *_report_filters(
                user_id, is_admin, keyword, market, stock_code, start_date, end_date
            )
        )
    )


async def get_analysis_task_by_task_id(session, task_id: str) -> dict[str, Any] | None:
    result = await session.execute(build_analysis_task_by_task_id_select(task_id))
    row = result.scalars().first()
    return _task_to_dict(row) if row else None


async def get_analysis_report_by_task_id(
    session, task_id: str
) -> dict[str, Any] | None:
    result = await session.execute(build_analysis_report_by_task_id_select(task_id))
    row = result.scalars().first()
    return _report_to_dict(row) if row else None


async def get_analysis_report_by_analysis_id(
    session, analysis_id: str
) -> dict[str, Any] | None:
    result = await session.execute(
        build_analysis_report_by_analysis_id_select(analysis_id)
    )
    row = result.scalars().first()
    return _report_to_dict(row) if row else None


async def list_user_analysis_tasks(
    session,
    user_id: str,
    *,
    status: str | None = None,
    batch_id: str | None = None,
    limit: int,
    offset: int = 0,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_user_analysis_tasks_select(
            user_id, status=status, batch_id=batch_id, limit=limit, offset=offset
        )
    )
    return [_task_to_dict(row) for row in result.scalars()]


async def list_user_analysis_reports(
    session,
    *,
    user_id: str | None,
    is_admin: bool,
    keyword: str | None = None,
    market: str | None = None,
    stock_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    filters = {
        "user_id": user_id,
        "is_admin": is_admin,
        "keyword": keyword,
        "market": market,
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
    }
    total = int(
        (
            await session.execute(build_user_analysis_reports_count_select(**filters))
        ).scalar_one()
    )
    result = await session.execute(
        build_user_analysis_reports_page_select(
            **filters,
            limit=limit,
            offset=offset,
        )
    )
    return ([dict(row) for row in result.mappings()], total)


def _report_filters(
    user_id: str | None,
    is_admin: bool,
    keyword: str | None,
    market: str | None,
    stock_code: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[Any]:
    deleted_flag = AnalysisReport.payload["deleted"].astext
    conditions: list[Any] = [or_(deleted_flag.is_(None), deleted_flag != "true")]
    if not is_admin:
        conditions.append(AnalysisReport.user_id == user_id)
    if keyword:
        pattern = f"%{keyword}%"
        conditions.append(
            or_(
                AnalysisReport.stock_symbol.ilike(pattern),
                AnalysisReport.analysis_id.ilike(pattern),
                AnalysisReport.summary.ilike(pattern),
            )
        )
    if market:
        conditions.append(AnalysisReport.payload["market_type"].astext == market)
    if stock_code:
        conditions.append(AnalysisReport.stock_symbol == stock_code)
    if start_date:
        conditions.append(
            AnalysisReport.analysis_date >= date.fromisoformat(start_date)
        )
    if end_date:
        conditions.append(AnalysisReport.analysis_date <= date.fromisoformat(end_date))
    return conditions


def _task_to_dict(row: AnalysisTask) -> dict[str, Any]:
    payload = row.payload or {}
    data = {
        **payload,
        "legacy_id": row.legacy_id,
        "task_id": row.task_id,
        "batch_id": payload.get("batch_id"),
        "user_id": row.user_id,
        "stock_symbol": row.stock_symbol,
        "symbol": payload.get("symbol") or row.stock_symbol,
        "stock_code": payload.get("stock_code") or row.stock_symbol,
        "status": row.status,
        "progress": row.progress,
        "created_at": payload.get("created_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at")
        or (row.updated_at.isoformat() if row.updated_at else None),
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
        "analysis_date": payload.get("analysis_date")
        or (row.analysis_date.isoformat() if row.analysis_date else None),
        "summary": row.summary,
        "created_at": payload.get("created_at")
        or (row.created_at.isoformat() if row.created_at else None),
        "updated_at": payload.get("updated_at")
        or (row.updated_at.isoformat() if row.updated_at else None),
    }
    data.pop("_id", None)
    return {key: value for key, value in data.items() if value is not None}
