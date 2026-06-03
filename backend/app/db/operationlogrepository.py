from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, desc, extract, func, or_, select

from app.db.dbmodels import OperationLogDocument
from app.models.operationlog import OperationLogStats


def build_operation_log_select(query, *, offset: int, limit: int) -> Select:
    return (
        select(OperationLogDocument)
        .where(*_filters(query))
        .order_by(desc(OperationLogDocument.timestamp))
        .offset(offset)
        .limit(limit)
    )


def build_operation_log_count(query) -> Select:
    return select(func.count()).select_from(OperationLogDocument).where(*_filters(query))


def build_operation_log_totals_select(days: int) -> Select:
    return select(
        func.count().label("total_logs"),
        func.coalesce(
            func.sum(case((OperationLogDocument.success.is_(True), 1), else_=0)),
            0,
        ).label("success_logs"),
    ).where(*_stats_filters(days))


def build_operation_log_action_distribution_select(days: int) -> Select:
    return (
        select(OperationLogDocument.action_type, func.count().label("count"))
        .where(*_stats_filters(days))
        .group_by(OperationLogDocument.action_type)
        .order_by(desc(func.count()))
    )


def build_operation_log_hourly_distribution_select(days: int) -> Select:
    hour = extract("hour", OperationLogDocument.timestamp).label("hour")
    return (
        select(hour, func.count().label("count"))
        .where(*_stats_filters(days))
        .group_by(hour)
        .order_by(hour)
    )


async def list_operation_logs(session, query) -> tuple[list[dict[str, Any]], int]:
    total_result = await session.execute(build_operation_log_count(query))
    total = int(total_result.scalar_one())

    offset = (query.page - 1) * query.page_size
    rows_result = await session.execute(
        build_operation_log_select(query, offset=offset, limit=query.page_size)
    )
    return [_operation_log_to_dict(row) for row in rows_result.scalars()], total


async def get_operation_log_stats(session, days: int) -> OperationLogStats:
    totals_result = await session.execute(build_operation_log_totals_select(days))
    totals = totals_result.one()
    total_logs = int(totals.total_logs or 0)
    success_logs = int(totals.success_logs or 0)
    failed_logs = total_logs - success_logs
    success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0

    action_rows = await session.execute(build_operation_log_action_distribution_select(days))
    action_type_distribution = {
        str(action_type): int(count)
        for action_type, count in action_rows
        if action_type is not None
    }

    hourly_rows = await session.execute(build_operation_log_hourly_distribution_select(days))
    hourly_data = {hour: 0 for hour in range(24)}
    for hour, count in hourly_rows:
        if hour is not None:
            hourly_data[int(hour)] = int(count)

    return OperationLogStats(
        total_logs=total_logs,
        success_logs=success_logs,
        failed_logs=failed_logs,
        success_rate=round(success_rate, 2),
        action_type_distribution=action_type_distribution,
        hourly_distribution=[
            {"hour": f"{hour:02d}:00", "count": count}
            for hour, count in hourly_data.items()
        ],
    )


def _filters(query) -> list[Any]:
    filters = [OperationLogDocument.deleted.is_(False)]

    if query.start_date:
        filters.append(OperationLogDocument.timestamp >= _parse_datetime(query.start_date))
    if query.end_date:
        filters.append(OperationLogDocument.timestamp <= _parse_datetime(query.end_date))
    if query.action_type:
        filters.append(OperationLogDocument.action_type == query.action_type)
    if query.success is not None:
        filters.append(OperationLogDocument.success == query.success)
    if query.user_id:
        filters.append(OperationLogDocument.user_id == query.user_id)
    if query.keyword:
        keyword = f"%{query.keyword}%"
        filters.append(
            or_(
                OperationLogDocument.username.ilike(keyword),
                OperationLogDocument.payload["action"].astext.ilike(keyword),
                OperationLogDocument.payload["details"]["stock_symbol"].astext.ilike(keyword),
            )
        )

    return filters


def _stats_filters(days: int) -> list[Any]:
    start_date = datetime.now() - timedelta(days=days)
    return [
        OperationLogDocument.deleted.is_(False),
        OperationLogDocument.timestamp >= start_date,
    ]


def _operation_log_to_dict(row: OperationLogDocument) -> dict[str, Any]:
    payload = row.payload or {}
    created_at = payload.get("created_at") or (row.created_at.isoformat() if row.created_at else None)
    timestamp = payload.get("timestamp") or (row.timestamp.isoformat() if row.timestamp else created_at)
    data = {
        **payload,
        "id": str(payload.get("_id") or row.legacy_id),
        "legacy_id": row.legacy_id,
        "user_id": row.user_id,
        "username": row.username,
        "action_type": row.action_type,
        "success": row.success,
        "timestamp": timestamp,
        "created_at": created_at or timestamp,
    }
    data.pop("_id", None)
    return {key: value for key, value in data.items() if value is not None}


def _parse_datetime(value: str) -> datetime:
    text = value.replace("Z", "")
    return datetime.fromisoformat(text)
