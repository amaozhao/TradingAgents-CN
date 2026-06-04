from __future__ import annotations

from typing import Any

from sqlalchemy import Select, and_, asc, desc, func, literal, select

from app.models.table import MarketQuote, StockBasicInfo, StockFinancialData

FIELD_COLUMNS = {
    "code": StockBasicInfo.code,
    "symbol": StockBasicInfo.code,
    "name": StockBasicInfo.name,
    "industry": StockBasicInfo.industry,
    "area": StockBasicInfo.area,
    "market": StockBasicInfo.market,
    "list_date": StockBasicInfo.list_date,
    "total_mv": StockBasicInfo.total_mv,
    "circ_mv": StockBasicInfo.circ_mv,
    "market_cap": StockBasicInfo.total_mv,
    "pe": StockBasicInfo.pe,
    "pb": StockBasicInfo.pb,
    "pe_ttm": StockBasicInfo.pe_ttm,
    "pb_mrq": StockBasicInfo.pb_mrq,
    "roe": StockFinancialData.roe,
    "roa": StockFinancialData.roa,
    "netprofit_margin": StockFinancialData.netprofit_margin,
    "gross_margin": StockFinancialData.gross_margin,
    "pct_chg": MarketQuote.pct_chg,
    "amount": MarketQuote.amount,
    "close": MarketQuote.close,
    "volume": MarketQuote.volume,
    "open": MarketQuote.open,
    "high": MarketQuote.high,
    "low": MarketQuote.low,
}


def build_screening_select(
    *,
    conditions: list[dict[str, Any]],
    limit: int,
    offset: int,
    order_by: list[dict[str, str]] | None,
    source: str,
) -> Select:
    statement = _base_select().where(*_filters(conditions, source))

    for order in _order_by(order_by):
        statement = statement.order_by(order)

    return statement.limit(limit).offset(offset)


def build_screening_count(*, conditions: list[dict[str, Any]], source: str) -> Select:
    return (
        select(func.count())
        .select_from(StockBasicInfo)
        .outerjoin(
            MarketQuote,
            and_(
                MarketQuote.code == StockBasicInfo.code,
                MarketQuote.source == StockBasicInfo.source,
            ),
        )
        .outerjoin(
            StockFinancialData,
            and_(
                StockFinancialData.code == StockBasicInfo.code,
                StockFinancialData.data_source == StockBasicInfo.source,
            ),
        )
        .where(*_filters(conditions, source))
    )


async def screen_stocks(
    session, *, conditions, limit: int, offset: int, order_by, source: str
):
    total_result = await session.execute(
        build_screening_count(conditions=conditions, source=source)
    )
    total = total_result.scalar_one()

    rows_result = await session.execute(
        build_screening_select(
            conditions=conditions,
            limit=limit,
            offset=offset,
            order_by=order_by,
            source=source,
        )
    )
    return [dict(row) for row in rows_result.mappings()], total


def _base_select() -> Select:
    return (
        select(
            StockBasicInfo.code.label("code"),
            StockBasicInfo.name.label("name"),
            StockBasicInfo.industry.label("industry"),
            StockBasicInfo.area.label("area"),
            StockBasicInfo.market.label("market"),
            StockBasicInfo.list_date.label("list_date"),
            StockBasicInfo.total_mv.label("total_mv"),
            StockBasicInfo.circ_mv.label("circ_mv"),
            StockBasicInfo.pe.label("pe"),
            StockBasicInfo.pb.label("pb"),
            StockBasicInfo.pe_ttm.label("pe_ttm"),
            StockBasicInfo.pb_mrq.label("pb_mrq"),
            StockFinancialData.roe.label("roe"),
            StockFinancialData.roa.label("roa"),
            StockFinancialData.netprofit_margin.label("netprofit_margin"),
            StockFinancialData.gross_margin.label("gross_margin"),
            MarketQuote.close.label("close"),
            MarketQuote.pct_chg.label("pct_chg"),
            MarketQuote.amount.label("amount"),
            MarketQuote.volume.label("volume"),
            MarketQuote.open.label("open"),
            MarketQuote.high.label("high"),
            MarketQuote.low.label("low"),
            StockBasicInfo.source.label("source"),
            StockBasicInfo.updated_at.label("updated_at"),
            literal(None).label("turnover_rate"),
            literal(None).label("volume_ratio"),
        )
        .select_from(StockBasicInfo)
        .outerjoin(
            MarketQuote,
            and_(
                MarketQuote.code == StockBasicInfo.code,
                MarketQuote.source == StockBasicInfo.source,
            ),
        )
        .outerjoin(
            StockFinancialData,
            and_(
                StockFinancialData.code == StockBasicInfo.code,
                StockFinancialData.data_source == StockBasicInfo.source,
            ),
        )
    )


def _filters(conditions: list[dict[str, Any]], source: str):
    filters = [StockBasicInfo.source == source]
    for condition in conditions:
        expression = _condition_expression(condition)
        if expression is not None:
            filters.append(expression)
    return filters


def _condition_expression(condition: dict[str, Any]):
    field = condition.get("field")
    if not isinstance(field, str):
        return None
    operator = str(condition.get("operator"))
    value = condition.get("value")
    column = FIELD_COLUMNS.get(field)
    if column is None:
        return None

    if operator == "between" and isinstance(value, list) and len(value) == 2:
        return and_(column >= value[0], column <= value[1])
    if operator == "contains":
        return column.ilike(f"%{value}%")
    if operator == "in" and isinstance(value, list):
        return column.in_(value)
    if operator == "not_in" and isinstance(value, list):
        return column.not_in(value)
    if operator == ">":
        return column > value
    if operator == "<":
        return column < value
    if operator == ">=":
        return column >= value
    if operator == "<=":
        return column <= value
    if operator == "==":
        return column == value
    if operator == "!=":
        return column != value
    return None


def _order_by(order_by: list[dict[str, str]] | None):
    if not order_by:
        return [desc(StockBasicInfo.total_mv)]

    orders = []
    for order in order_by:
        field = order.get("field")
        column = FIELD_COLUMNS.get(field) if field else None
        if column is None:
            continue
        direction = order.get("direction", "desc").lower()
        orders.append(asc(column) if direction == "asc" else desc(column))
    return orders or [desc(StockBasicInfo.total_mv)]
