from __future__ import annotations

import importlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.database import get_postgres_db
from app.core.response import ok
from app.db.dual import dual_write_hot_document
from app.routers.account import get_current_user
from app.schemas.response import ApiResponse
from app.schemas.stocks import BatchStockSyncRequest, SingleStockSyncRequest

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/stock-sync", tags=["股票数据同步"])
get_tushare_sync_service = getattr(
    importlib.import_module("app.worker.tushare.sync"), "get_tushare_sync_service"
)
get_akshare_sync_service = getattr(
    importlib.import_module("app.worker.akshare.sync"), "get_akshare_sync_service"
)
get_financial_sync_service = getattr(
    importlib.import_module("app.worker.financial"), "get_financial_sync_service"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _dual_write_stock_basic_info(document: dict[str, Any]) -> None:
    await dual_write_hot_document(
        "stock_basic_info", document, enabled=True, fail_open=True
    )


def _sync_result_from_stats(stats: dict[str, Any], source: str) -> dict[str, Any]:
    errors = stats.get("errors") or []
    first_error = errors[0] if errors else {}
    error_message = (
        first_error.get("error")
        if isinstance(first_error, dict)
        else str(first_error) if first_error else None
    )
    success = int(stats.get("success_count") or 0) > 0
    return {
        "success": success,
        "records": stats.get("success_count", 0),
        "message": f"成功 {stats.get('success_count', 0)}/{stats.get('total_processed', 0)}",
        "error": None if success else error_message or "同步失败",
        "data_source_used": "akshare"
        if stats.get("switched_to_akshare")
        else source,
        "attempted_sources": ["tushare", "akshare"]
        if stats.get("switched_to_akshare")
        else [source],
        "market_quote_available": success,
    }


@router.post("/single", response_model=ApiResponse)
async def sync_single_stock(
    request: SingleStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """同步单只股票的实时、历史、财务和基础数据。"""
    raw_symbol = str(request.symbol).strip().upper()
    symbol = raw_symbol.zfill(6) if raw_symbol.isdigit() else raw_symbol
    result: dict[str, Any] = {
        "symbol": symbol,
        "realtime_sync": None,
        "historical_sync": None,
        "financial_sync": None,
        "basic_sync": None,
        "overall_success": False,
    }

    try:
        if request.sync_realtime:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")
                stats = await service.sync_realtime_quotes(symbols=[symbol], force=True)
                result["realtime_sync"] = _sync_result_from_stats(
                    stats, request.data_source
                )
            except Exception as e:
                logger.error(f"❌ 单股实时行情同步失败 {symbol}: {e}")
                result["realtime_sync"] = {
                    "success": False,
                    "records": 0,
                    "error": str(e),
                    "message": "实时行情同步失败",
                    "data_source_used": request.data_source,
                    "attempted_sources": [request.data_source],
                    "market_quote_available": False,
                }

        if request.sync_historical or request.sync_financial or request.sync_basic:
            batch_response = await sync_batch_stocks(
                BatchStockSyncRequest(
                    symbols=[symbol],
                    sync_historical=request.sync_historical,
                    sync_financial=request.sync_financial,
                    sync_basic=request.sync_basic,
                    data_source=request.data_source,
                    days=request.days,
                ),
                background_tasks,
                current_user,
            )
            batch_data = batch_response.get("data", {})
            result["historical_sync"] = batch_data.get("historical_sync")
            result["financial_sync"] = batch_data.get("financial_sync")
            result["basic_sync"] = batch_data.get("basic_sync")

        selected_results = [
            result.get("realtime_sync") if request.sync_realtime else None,
            result.get("historical_sync") if request.sync_historical else None,
            result.get("financial_sync") if request.sync_financial else None,
            result.get("basic_sync") if request.sync_basic else None,
        ]
        result["overall_success"] = any(
            item
            and (
                item.get("success")
                or item.get("success_count", 0) > 0
            )
            for item in selected_results
            if isinstance(item, dict)
        )

        return ok(
            data=result,
            message="单股同步完成" if result["overall_success"] else "单股同步完成，部分或全部数据未成功",
        )
    except Exception as e:
        logger.error(f"❌ 单股同步失败 {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"单股同步失败: {str(e)}")


@router.post("/batch", response_model=ApiResponse)
async def sync_batch_stocks(
    request: BatchStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    批量同步多个股票的历史数据和财务数据

    - **symbols**: 股票代码列表
    - **sync_historical**: 是否同步历史数据
    - **sync_financial**: 是否同步财务数据
    - **data_source**: 数据源（tushare/akshare）
    - **days**: 历史数据天数
    """
    try:
        logger.info(
            f"📊 开始批量同步 {len(request.symbols)} 只股票 (数据源: {request.data_source})"
        )

        result = {
            "total": len(request.symbols),
            "symbols": request.symbols,
            "historical_sync": None,
            "financial_sync": None,
            "basic_sync": None,
        }

        # 同步历史数据
        if request.sync_historical:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")

                # 计算日期范围
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=request.days)).strftime(
                    "%Y-%m-%d"
                )

                # 批量同步历史数据
                hist_result = await service.sync_historical_data(
                    symbols=request.symbols,
                    start_date=start_date,
                    end_date=end_date,
                    incremental=False,
                )

                result["historical_sync"] = {
                    "success_count": hist_result.get("success_count", 0),
                    "error_count": hist_result.get("error_count", 0),
                    "total_records": hist_result.get("total_records", 0),
                    "message": f"成功同步 {hist_result.get('success_count', 0)}/{len(request.symbols)} 只股票，共 {hist_result.get('total_records', 0)} 条记录",
                }
                logger.info(
                    f"✅ 批量历史数据同步完成: {hist_result.get('success_count', 0)}/{len(request.symbols)}"
                )

            except Exception as e:
                logger.error(f"❌ 批量历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e),
                }

        # 同步财务数据
        if request.sync_financial:
            try:
                financial_service = await get_financial_sync_service()

                # 批量同步财务数据
                fin_results = await financial_service.sync_financial_data(
                    symbols=request.symbols,
                    data_sources=[request.data_source],
                    batch_size=10,
                )

                source_stats = fin_results.get(request.data_source)
                if source_stats:
                    result["financial_sync"] = {
                        "success_count": source_stats.success_count,
                        "error_count": source_stats.error_count,
                        "total_symbols": source_stats.total_symbols,
                        "message": f"成功同步 {source_stats.success_count}/{source_stats.total_symbols} 只股票的财务数据",
                    }
                else:
                    result["financial_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "message": "财务数据同步失败",
                    }

                logger.info(
                    f"✅ 批量财务数据同步完成: {result['financial_sync']['success_count']}/{len(request.symbols)}"
                )

            except Exception as e:
                logger.error(f"❌ 批量财务数据同步失败: {e}")
                result["financial_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e),
                }

        # 同步基础数据
        if request.sync_basic:
            try:
                # 🔥 批量同步基础数据
                # 注意：基础数据同步服务目前只支持 Tushare 数据源
                if request.data_source == "tushare":
                    TushareProvider = getattr(
                        importlib.import_module("trader.flows.providers.china.tushare"),
                        "TushareProvider",
                    )

                    tushare_provider = TushareProvider()
                    if tushare_provider.is_available():
                        success_count = 0
                        error_count = 0

                        for symbol in request.symbols:
                            try:
                                basic_info = (
                                    await tushare_provider.get_stock_basic_info(symbol)
                                )

                                if isinstance(basic_info, dict):
                                    # 保存到 PostgreSQL
                                    db = get_postgres_db()
                                    symbol6 = str(symbol).zfill(6)

                                    # 添加必要字段
                                    basic_info["code"] = symbol6
                                    basic_info["source"] = "tushare"
                                    basic_info["updated_at"] = _utc_now()

                                    await db.stock_basic_info.update_one(
                                        {"code": symbol6, "source": "tushare"},
                                        {"$set": basic_info},
                                        upsert=True,
                                    )
                                    await _dual_write_stock_basic_info(basic_info)

                                    success_count += 1
                                    logger.info(f"✅ {symbol} 基础数据同步成功")
                                else:
                                    error_count += 1
                                    logger.warning(f"⚠️ {symbol} 未获取到基础数据")
                            except Exception as e:
                                error_count += 1
                                logger.error(f"❌ {symbol} 基础数据同步失败: {e}")

                        result["basic_sync"] = {
                            "success_count": success_count,
                            "error_count": error_count,
                            "total_symbols": len(request.symbols),
                            "message": f"成功同步 {success_count}/{len(request.symbols)} 只股票的基础数据",
                        }
                        logger.info(
                            f"✅ 批量基础数据同步完成: {success_count}/{len(request.symbols)}"
                        )
                    else:
                        result["basic_sync"] = {
                            "success_count": 0,
                            "error_count": len(request.symbols),
                            "error": "Tushare 数据源不可用",
                        }
                else:
                    result["basic_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "error": f"基础数据同步仅支持 Tushare 数据源，当前数据源: {request.data_source}",
                    }

            except Exception as e:
                logger.error(f"❌ 批量基础数据同步失败: {e}")
                result["basic_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e),
                }

        # 判断整体是否成功
        hist_success = (
            result["historical_sync"].get("success_count", 0)
            if request.sync_historical
            else 0
        )
        fin_success = (
            result["financial_sync"].get("success_count", 0)
            if request.sync_financial
            else 0
        )
        basic_success = (
            result["basic_sync"].get("success_count", 0) if request.sync_basic else 0
        )
        total_success = max(hist_success, fin_success, basic_success)

        # 添加统计信息到结果中
        result["total_success"] = total_success
        result["total_symbols"] = len(request.symbols)

        return ok(
            data=result,
            message=f"批量同步完成: {total_success}/{len(request.symbols)} 只股票成功",
        )

    except Exception as e:
        logger.error(f"❌ 批量同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量同步失败: {str(e)}")


@router.get("/status/{symbol}", response_model=ApiResponse)
async def get_sync_status(symbol: str, current_user: dict = Depends(get_current_user)):
    """
    获取股票的同步状态

    返回最后同步时间、数据条数等信息
    """
    try:
        get_postgres_db = getattr(
            importlib.import_module("app.core.database"), "get_postgres_db"
        )

        db = get_postgres_db()

        # 查询历史数据最后同步时间
        hist_doc = await db.historical_data.find_one(
            {"symbol": symbol}, sort=[("date", -1)]
        )

        # 查询财务数据最后同步时间
        fin_doc = await db.stock_financial_data.find_one(
            {"symbol": symbol}, sort=[("updated_at", -1)]
        )

        # 统计历史数据条数
        hist_count = await db.historical_data.count_documents({"symbol": symbol})

        # 统计财务数据条数
        fin_count = await db.stock_financial_data.count_documents({"symbol": symbol})

        return ok(
            data={
                "symbol": symbol,
                "historical_data": {
                    "last_sync": hist_doc.get("updated_at") if hist_doc else None,
                    "last_date": hist_doc.get("date") if hist_doc else None,
                    "total_records": hist_count,
                },
                "financial_data": {
                    "last_sync": fin_doc.get("updated_at") if fin_doc else None,
                    "last_report_period": fin_doc.get("report_period")
                    if fin_doc
                    else None,
                    "total_records": fin_count,
                },
            }
        )

    except Exception as e:
        logger.error(f"❌ 获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取同步状态失败: {str(e)}")
