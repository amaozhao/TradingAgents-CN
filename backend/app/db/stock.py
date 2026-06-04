from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, desc, or_, select

from app.db.model import MarketQuote, StockBasicInfo, StockDailyQuote

SOURCE_PRIORITY = ("tushare", "multi_source", "akshare", "baostock")


def build_get_stock_basic_info(symbol: str, source: str | None = None) -> Select:
    code = _lookup_code(symbol)
    statement = select(StockBasicInfo).where(StockBasicInfo.code == code)
    if source:
        statement = statement.where(StockBasicInfo.source == source)
    else:
        statement = statement.order_by(_source_priority_case())
    return statement.limit(1)


def build_get_market_quote(symbol: str) -> Select:
    code = _lookup_code(symbol)
    return (
        select(MarketQuote)
        .where(MarketQuote.code == code)
        .order_by(desc(MarketQuote.updated_at))
        .limit(1)
    )


def build_stock_list(
    *,
    source: str,
    market: str | None,
    industry: str | None,
    page: int,
    page_size: int,
) -> Select:
    statement = select(StockBasicInfo).where(StockBasicInfo.source == source)
    if market:
        statement = statement.where(StockBasicInfo.market == market)
    if industry:
        statement = statement.where(StockBasicInfo.industry == industry)
    return (
        statement.order_by(desc(StockBasicInfo.total_mv))
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    )


def build_search_stocks(query: str, *, limit: int) -> Select:
    pattern = f"%{str(query).strip()}%"
    return (
        select(StockBasicInfo)
        .where(
            or_(
                StockBasicInfo.code.ilike(pattern),
                StockBasicInfo.name.ilike(pattern),
            )
        )
        .order_by(_source_priority_case(), desc(StockBasicInfo.total_mv))
        .limit(limit)
    )


def build_list_stock_daily_quotes(
    *,
    market: str | None,
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    data_source: str | None = None,
    period: str | None = None,
    limit: int = 100,
) -> Select:
    lookup_code = _lookup_code(code)
    codes = {str(code).strip().upper(), lookup_code}
    statement = select(StockDailyQuote).where(
        or_(StockDailyQuote.symbol.in_(codes), StockDailyQuote.code.in_(codes))
    )
    if market:
        statement = statement.where(StockDailyQuote.market == market)
    if start_date:
        statement = statement.where(
            StockDailyQuote.trade_date >= _date_from_string(start_date)
        )
    if end_date:
        statement = statement.where(
            StockDailyQuote.trade_date <= _date_from_string(end_date)
        )
    if data_source:
        statement = statement.where(StockDailyQuote.data_source == data_source)
    if period:
        statement = statement.where(StockDailyQuote.period == period)
    return statement.order_by(desc(StockDailyQuote.trade_date)).limit(limit)


async def get_stock_basic_info(
    session, symbol: str, source: str | None = None
) -> dict[str, Any] | None:
    result = await session.execute(build_get_stock_basic_info(symbol, source))
    row = result.scalar_one_or_none()
    return _basic_info_to_dict(row) if row else None


async def get_market_quote(session, symbol: str) -> dict[str, Any] | None:
    result = await session.execute(build_get_market_quote(symbol))
    row = result.scalar_one_or_none()
    return _market_quote_to_dict(row) if row else None


async def list_stocks(
    session,
    *,
    source: str,
    market: str | None,
    industry: str | None,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_stock_list(
            source=source,
            market=market,
            industry=industry,
            page=page,
            page_size=page_size,
        )
    )
    return [_basic_info_to_dict(row) for row in result.scalars()]


async def search_stocks(
    session, query: str, *, limit: int = 20
) -> list[dict[str, Any]]:
    result = await session.execute(build_search_stocks(query, limit=limit))
    seen_codes: set[str] = set()
    documents: list[dict[str, Any]] = []
    for row in result.scalars():
        if row.code in seen_codes:
            continue
        seen_codes.add(row.code)
        documents.append(_basic_info_to_dict(row))
    return documents


async def list_stock_daily_quotes(
    session,
    *,
    market: str | None,
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    data_source: str | None = None,
    period: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    result = await session.execute(
        build_list_stock_daily_quotes(
            market=market,
            code=code,
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
            period=period,
            limit=limit,
        )
    )
    return [_daily_quote_to_dict(row) for row in result.scalars()]


def _basic_info_to_dict(row: StockBasicInfo) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "code": row.code,
        "symbol": row.code,
        "source": row.source,
        "name": row.name,
        "industry": row.industry,
        "area": row.area,
        "market": row.market,
        "list_date": row.list_date.isoformat() if row.list_date else None,
        "total_mv": _json_number(row.total_mv),
        "circ_mv": _json_number(row.circ_mv),
        "pe": _json_number(row.pe),
        "pb": _json_number(row.pb),
        "pe_ttm": _json_number(row.pe_ttm),
        "pb_mrq": _json_number(row.pb_mrq),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return {key: value for key, value in data.items() if value is not None}


def _daily_quote_to_dict(row: StockDailyQuote) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "symbol": row.symbol,
        "code": row.code or row.symbol,
        "full_symbol": row.full_symbol,
        "market": row.market,
        "trade_date": row.trade_date.isoformat() if row.trade_date else None,
        "period": row.period,
        "data_source": row.data_source,
        "open": _json_number(row.open),
        "high": _json_number(row.high),
        "low": _json_number(row.low),
        "close": _json_number(row.close),
        "pre_close": _json_number(row.pre_close),
        "volume": _json_number(row.volume),
        "amount": _json_number(row.amount),
        "change": _json_number(row.change),
        "pct_chg": _json_number(row.pct_chg),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return {key: value for key, value in data.items() if value is not None}


def _market_quote_to_dict(row: MarketQuote) -> dict[str, Any]:
    data = {
        **(row.payload or {}),
        "legacy_id": row.legacy_id,
        "code": row.code,
        "symbol": row.code,
        "source": row.source,
        "trade_date": row.trade_date.isoformat() if row.trade_date else None,
        "open": _json_number(row.open),
        "high": _json_number(row.high),
        "low": _json_number(row.low),
        "close": _json_number(row.close),
        "pre_close": _json_number(row.pre_close),
        "pct_chg": _json_number(row.pct_chg),
        "amount": _json_number(row.amount),
        "volume": _json_number(row.volume),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return {key: value for key, value in data.items() if value is not None}


def _json_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _lookup_code(symbol: str) -> str:
    code = str(symbol).strip().upper()
    if code.isdigit() and len(code) < 5:
        return code.zfill(6)
    return code


def _date_from_string(value: str) -> date:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return date.fromisoformat(text[:10])


def _source_priority_case():
    case = getattr(importlib.import_module("sqlalchemy"), "case")

    return case(
        {source: index for index, source in enumerate(SOURCE_PRIORITY)},
        value=StockBasicInfo.source,
        else_=len(SOURCE_PRIORITY),
    )
