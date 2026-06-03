from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select

from app.db.analysis_repository import (
    get_analysis_report_by_task_id,
    get_analysis_task_by_task_id,
    list_user_analysis_tasks,
)
from app.db.financial_repository import get_financial_data
from app.db.message_repository import (
    get_internal_message_stats,
    get_social_media_stats,
    query_internal_messages,
    query_social_media_messages,
)
from app.db.models import (
    AnalysisTask,
    InternalMessageDocument,
    LoginAttemptDocument,
    OperationLogDocument,
    PaperAccount,
    PaperOrder,
    PaperPosition,
    SocialMediaMessageDocument,
    StockBasicInfo,
    StockFinancialData,
    StockNewsDocument,
    SystemConfigDocument,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)
from app.db.news_repository import query_news
from app.db.operation_log_repository import get_operation_log_stats, list_operation_logs
from app.db.paper_repository import get_paper_account, list_paper_orders, list_paper_positions
from app.db.session import close_postgres, get_session_factory, init_postgres
from app.db.stock_repository import (
    get_market_quote,
    get_stock_basic_info,
    list_stock_daily_quotes,
    list_stocks,
)
from app.db.user_preferences_repository import list_user_favorites, list_user_tags
from app.models.operation_log import OperationLogQuery


@dataclass
class SmokeResult:
    name: str
    passed: bool
    detail: str
    sample: Any = None


async def run_smoke() -> dict[str, Any]:
    await init_postgres()
    try:
        async with get_session_factory()() as session:
            context = await _discover_context(session)
            checks: list[SmokeResult] = []
            checkers: list[tuple[str, Callable[[Any, dict[str, Any]], Awaitable[SmokeResult]]]] = [
                ("stock_basic_info", _check_stock_basic_info),
                ("stock_list", _check_stock_list),
                ("market_quote", _check_market_quote),
                ("daily_quotes", _check_daily_quotes),
                ("financial_data", _check_financial_data),
                ("analysis_task_report", _check_analysis),
                ("user_preferences", _check_user_preferences),
                ("paper_trading", _check_paper),
                ("operation_logs", _check_operation_logs),
                ("stock_news", _check_news),
                ("messages", _check_messages),
                ("security_sessions", _check_security_sessions),
                ("system_configs", _check_system_configs),
            ]

            for name, checker in checkers:
                try:
                    checks.append(await checker(session, context))
                except Exception as exc:  # pragma: no cover - exercised by CLI failures
                    checks.append(SmokeResult(name=name, passed=False, detail=str(exc)))

            return {
                "all_passed": all(check.passed for check in checks),
                "context": context,
                "checks": [asdict(check) for check in checks],
            }
    finally:
        await close_postgres()


async def _discover_context(session) -> dict[str, Any]:
    stock = await _first_model(session, StockBasicInfo, StockBasicInfo.code.is_not(None))
    financial = await _first_model(session, StockFinancialData, StockFinancialData.code.is_not(None))
    analysis = await _first_model(session, AnalysisTask, AnalysisTask.task_id.is_not(None))
    favorite = await _first_model(session, UserFavorite, UserFavorite.user_id.is_not(None))
    tag = await _first_model(session, UserTag, UserTag.user_id.is_not(None))
    paper_account = await _first_model(session, PaperAccount, PaperAccount.user_id.is_not(None))
    paper_position = await _first_model(session, PaperPosition, PaperPosition.user_id.is_not(None))
    paper_order = await _first_model(session, PaperOrder, PaperOrder.user_id.is_not(None))
    operation_log = await _first_model(session, OperationLogDocument, OperationLogDocument.deleted.is_(False))
    news = await _first_model(session, StockNewsDocument, StockNewsDocument.deleted.is_(False))
    internal_message = await _first_model(session, InternalMessageDocument, InternalMessageDocument.deleted.is_(False))
    social_message = await _first_model(session, SocialMediaMessageDocument, SocialMediaMessageDocument.deleted.is_(False))

    return {
        "stock_code": getattr(stock, "code", None) or getattr(financial, "code", None),
        "stock_source": getattr(stock, "source", None),
        "financial_code": getattr(financial, "code", None) or getattr(stock, "code", None),
        "financial_source": getattr(financial, "data_source", None),
        "analysis_task_id": getattr(analysis, "task_id", None),
        "analysis_user_id": getattr(analysis, "user_id", None),
        "favorite_user_id": getattr(favorite, "user_id", None) or getattr(tag, "user_id", None),
        "paper_user_id": (
            getattr(paper_account, "user_id", None)
            or getattr(paper_position, "user_id", None)
            or getattr(paper_order, "user_id", None)
        ),
        "operation_user_id": getattr(operation_log, "user_id", None),
        "operation_action_type": getattr(operation_log, "action_type", None),
        "news_symbol": getattr(news, "symbol", None),
        "internal_symbol": getattr(internal_message, "symbol", None),
        "social_symbol": getattr(social_message, "symbol", None),
    }


async def _check_stock_basic_info(session, context: dict[str, Any]) -> SmokeResult:
    code = _require(context.get("stock_code"), "stock code")
    document = await get_stock_basic_info(session, code, context.get("stock_source"))
    return _expect_document("stock_basic_info", document, ["legacy_id", "code"])


async def _check_stock_list(session, context: dict[str, Any]) -> SmokeResult:
    source = _require(context.get("stock_source"), "stock source")
    rows = await list_stocks(session, source=source, market=None, industry=None, page=1, page_size=5)
    return _expect_non_empty("stock_list", rows)


async def _check_market_quote(session, context: dict[str, Any]) -> SmokeResult:
    code = _require(context.get("stock_code"), "stock code")
    document = await get_market_quote(session, code)
    return _expect_document("market_quote", document, ["legacy_id", "code"])


async def _check_daily_quotes(session, context: dict[str, Any]) -> SmokeResult:
    code = _require(context.get("stock_code"), "stock code")
    rows = await list_stock_daily_quotes(session, market=None, code=code, limit=5)
    return _expect_non_empty("daily_quotes", rows)


async def _check_financial_data(session, context: dict[str, Any]) -> SmokeResult:
    code = _require(context.get("financial_code"), "financial code")
    rows = await get_financial_data(
        session,
        symbol=code,
        data_source=context.get("financial_source"),
        limit=5,
    )
    return _expect_non_empty("financial_data", rows)


async def _check_analysis(session, context: dict[str, Any]) -> SmokeResult:
    task_id = _require(context.get("analysis_task_id"), "analysis task id")
    task = await get_analysis_task_by_task_id(session, task_id)
    report = await get_analysis_report_by_task_id(session, task_id)
    if context.get("analysis_user_id"):
        tasks = await list_user_analysis_tasks(session, context["analysis_user_id"], limit=5)
    else:
        tasks = [task] if task else []
    if not task or not tasks:
        return SmokeResult("analysis_task_report", False, "analysis task read returned empty")
    return SmokeResult(
        "analysis_task_report",
        True,
        "analysis task read passed",
        {"task_id": task.get("task_id"), "has_report": bool(report), "user_task_count": len(tasks)},
    )


async def _check_user_preferences(session, context: dict[str, Any]) -> SmokeResult:
    user_id = _require(context.get("favorite_user_id"), "favorite/tag user id")
    favorites = await list_user_favorites(session, user_id)
    tags = await list_user_tags(session, user_id)
    if not favorites and not tags:
        return SmokeResult("user_preferences", False, "favorites and tags both returned empty")
    return SmokeResult(
        "user_preferences",
        True,
        "user preference read passed",
        {"favorites": len(favorites), "tags": len(tags)},
    )


async def _check_paper(session, context: dict[str, Any]) -> SmokeResult:
    user_id = _require(context.get("paper_user_id"), "paper user id")
    account = await get_paper_account(session, user_id)
    positions = await list_paper_positions(session, user_id)
    orders = await list_paper_orders(session, user_id, limit=5)
    if not account and not positions and not orders:
        return SmokeResult("paper_trading", False, "paper account/position/order reads all returned empty")
    return SmokeResult(
        "paper_trading",
        True,
        "paper trading read passed",
        {"has_account": bool(account), "positions": len(positions), "orders": len(orders)},
    )


async def _check_operation_logs(session, context: dict[str, Any]) -> SmokeResult:
    query = OperationLogQuery(
        page=1,
        page_size=5,
        user_id=context.get("operation_user_id"),
        action_type=context.get("operation_action_type"),
    )
    rows, total = await list_operation_logs(session, query)
    stats = await get_operation_log_stats(session, days=3650)
    if total <= 0 or not rows:
        return SmokeResult("operation_logs", False, "operation log read returned empty")
    return SmokeResult(
        "operation_logs",
        True,
        "operation log read passed",
        {"total": total, "stats_total": stats.total_logs},
    )


async def _check_news(session, context: dict[str, Any]) -> SmokeResult:
    params = SimpleNamespace(
        symbol=context.get("news_symbol"),
        symbols=None,
        start_time=None,
        end_time=None,
        category=None,
        sentiment=None,
        importance=None,
        data_source=None,
        keywords=None,
        sort_by="publish_time",
        sort_order=-1,
        skip=0,
        limit=5,
    )
    rows = await query_news(session, params)
    return _expect_non_empty("stock_news", rows)


async def _check_messages(session, context: dict[str, Any]) -> SmokeResult:
    internal_params = SimpleNamespace(
        symbol=context.get("internal_symbol"),
        symbols=None,
        message_type=None,
        category=None,
        source_type=None,
        department=None,
        author=None,
        start_time=None,
        end_time=None,
        importance=None,
        access_level=None,
        min_confidence=None,
        rating=None,
        keywords=None,
        tags=None,
        sort_by="created_time",
        sort_order=-1,
        skip=0,
        limit=5,
    )
    social_params = SimpleNamespace(
        symbol=context.get("social_symbol"),
        symbols=None,
        platform=None,
        message_type=None,
        start_time=None,
        end_time=None,
        sentiment=None,
        importance=None,
        min_influence_score=None,
        min_engagement_rate=None,
        verified_only=False,
        keywords=None,
        hashtags=None,
        sort_by="publish_time",
        sort_order=-1,
        skip=0,
        limit=5,
    )
    internal = await query_internal_messages(session, internal_params)
    social = await query_social_media_messages(session, social_params)
    internal_stats = await get_internal_message_stats(session, symbol=context.get("internal_symbol"))
    social_stats = await get_social_media_stats(session, symbol=context.get("social_symbol"))
    if not internal and not social:
        return SmokeResult("messages", False, "internal and social message reads both returned empty")
    return SmokeResult(
        "messages",
        True,
        "message reads passed",
        {
            "internal": len(internal),
            "social": len(social),
            "internal_stats_total": internal_stats["total_count"],
            "social_stats_total": social_stats["total_count"],
        },
    )


async def _check_security_sessions(session, _context: dict[str, Any]) -> SmokeResult:
    session_count = await _count(session, UserSessionDocument)
    attempt_count = await _count(session, LoginAttemptDocument)
    if session_count <= 0 and attempt_count <= 0:
        return SmokeResult("security_sessions", False, "user_sessions and login_attempts are both empty")
    return SmokeResult(
        "security_sessions",
        True,
        "security/session tables are populated",
        {"user_sessions": session_count, "login_attempts": attempt_count},
    )


async def _check_system_configs(session, _context: dict[str, Any]) -> SmokeResult:
    count = await _count(session, SystemConfigDocument)
    if count <= 0:
        return SmokeResult("system_configs", False, "system_config_documents is empty")
    return SmokeResult("system_configs", True, "system config documents are populated", {"count": count})


async def _first_model(session, model, *filters):
    result = await session.execute(select(model).where(*filters).limit(1))
    return result.scalars().first()


async def _count(session, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


def _expect_non_empty(name: str, rows: list[dict[str, Any]]) -> SmokeResult:
    if not rows:
        return SmokeResult(name, False, f"{name} returned empty")
    return SmokeResult(name, True, f"{name} read passed", {"count": len(rows), "first": rows[0]})


def _expect_document(name: str, document: dict[str, Any] | None, required_keys: list[str]) -> SmokeResult:
    if not document:
        return SmokeResult(name, False, f"{name} returned empty")
    missing = [key for key in required_keys if key not in document]
    if missing:
        return SmokeResult(name, False, f"{name} missing keys: {missing}", document)
    return SmokeResult(name, True, f"{name} read passed", document)


def _require(value: Any, label: str) -> Any:
    if value in {None, ""}:
        raise ValueError(f"missing {label}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test PostgreSQL primary-read cutover data paths.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = asyncio.run(run_smoke())
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
