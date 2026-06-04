from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, desc, select

from app.db.model import StockFinancialData


def build_financial_data_query(
    *,
    symbol: str,
    report_period: str | None = None,
    data_source: str | None = None,
    report_type: str | None = None,
    limit: int | None = None,
) -> Select:
    symbol6 = str(symbol).zfill(6)
    statement = select(StockFinancialData).where(StockFinancialData.code == symbol6)
    if report_period:
        statement = statement.where(StockFinancialData.report_period == report_period)
    if data_source:
        statement = statement.where(StockFinancialData.data_source == data_source)
    if report_type:
        statement = statement.where(
            StockFinancialData.payload["report_type"].astext == report_type
        )
    statement = statement.order_by(desc(StockFinancialData.report_period))
    if limit:
        statement = statement.limit(limit)
    return statement


async def get_financial_data(
    session,
    *,
    symbol: str,
    report_period: str | None = None,
    data_source: str | None = None,
    report_type: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_financial_data_query(
            symbol=symbol,
            report_period=report_period,
            data_source=data_source,
            report_type=report_type,
            limit=limit,
        )
    )
    return [_financial_row_to_dict(row) for row in result.scalars()]


def _financial_row_to_dict(row: StockFinancialData) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "code": row.code,
        "symbol": row.code,
        "data_source": row.data_source,
        "report_period": row.report_period,
        "roe": _json_number(row.roe),
        "roa": _json_number(row.roa),
        "netprofit_margin": _json_number(row.netprofit_margin),
        "gross_margin": _json_number(row.gross_margin),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return {key: value for key, value in data.items() if value is not None}


def _json_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
