from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.dialects.postgresql import insert

from app.db.document_mapper import (
    map_analysis_report,
    map_analysis_batch,
    map_analysis_result,
    map_analysis_task,
    map_database_backup,
    map_internal_message,
    map_login_attempt,
    map_market_quote,
    map_notification,
    map_operation_log,
    map_paper_account,
    map_paper_order,
    map_paper_position,
    map_paper_trade,
    map_scheduler_execution,
    map_scheduler_history,
    map_scheduler_metadata,
    map_stock_basic_info,
    map_stock_daily_quote,
    map_stock_financial_data,
    map_stock_news,
    map_system_config_document,
    map_sync_status,
    map_social_media_message,
    map_token_usage,
    map_user_account,
    map_user_favorite,
    map_user_session,
    map_user_tag,
)
from app.db.models import (
    AnalysisReport,
    AnalysisBatchDocument,
    AnalysisResultDocument,
    AnalysisTask,
    DatabaseBackupDocument,
    InternalMessageDocument,
    LoginAttemptDocument,
    MarketQuote,
    NotificationDocument,
    OperationLogDocument,
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperTrade,
    SchedulerExecution,
    SchedulerHistoryDocument,
    SchedulerMetadataDocument,
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SystemConfigDocument,
    SyncStatusDocument,
    SocialMediaMessageDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)


def build_stock_basic_info_upsert(document: dict[str, Any]):
    values = map_stock_basic_info(document)
    return _build_upsert(StockBasicInfo.__table__, values, ("code", "source"))


def build_market_quote_upsert(document: dict[str, Any]):
    values = map_market_quote(document)
    return _build_upsert(MarketQuote.__table__, values, ("code", "source"))


def build_stock_daily_quote_upsert(document: dict[str, Any]):
    values = map_stock_daily_quote(document)
    return _build_upsert(StockDailyQuote.__table__, values, ("symbol", "trade_date", "data_source", "period"))


def build_stock_financial_data_upsert(document: dict[str, Any]):
    values = map_stock_financial_data(document)
    return _build_upsert(StockFinancialData.__table__, values, ("code", "data_source", "report_period"))


def build_stock_news_upsert(document: dict[str, Any]):
    values = map_stock_news(document)
    return _build_upsert(StockNewsDocument.__table__, values, ("legacy_id",))


def build_analysis_task_upsert(document: dict[str, Any]):
    values = map_analysis_task(document)
    return _build_upsert(AnalysisTask.__table__, values, ("task_id",))


def build_analysis_report_upsert(document: dict[str, Any]):
    values = map_analysis_report(document)
    return _build_upsert(AnalysisReport.__table__, values, ("analysis_id",))


def build_analysis_batch_upsert(document: dict[str, Any]):
    values = map_analysis_batch(document)
    return _build_upsert(AnalysisBatchDocument.__table__, values, ("batch_id",))


def build_analysis_result_upsert(document: dict[str, Any]):
    values = map_analysis_result(document)
    return _build_upsert(AnalysisResultDocument.__table__, values, ("legacy_id",))


def build_sync_status_upsert(document: dict[str, Any]):
    values = map_sync_status(document)
    return _build_upsert(SyncStatusDocument.__table__, values, ("job",))


def build_scheduler_execution_upsert(document: dict[str, Any]):
    values = map_scheduler_execution(document)
    return _build_upsert(SchedulerExecution.__table__, values, ("legacy_id",))


def build_scheduler_history_upsert(document: dict[str, Any]):
    values = map_scheduler_history(document)
    return _build_upsert(SchedulerHistoryDocument.__table__, values, ("legacy_id",))


def build_scheduler_metadata_upsert(document: dict[str, Any]):
    values = map_scheduler_metadata(document)
    return _build_upsert(SchedulerMetadataDocument.__table__, values, ("job_id",))


def build_system_config_document_upsert(document: dict[str, Any], *, collection: str = "system_configs"):
    values = map_system_config_document(document, collection=collection)
    return _build_upsert(SystemConfigDocument.__table__, values, ("config_key",))


def build_user_favorite_upsert(document: dict[str, Any]):
    values = map_user_favorite(document)
    return _build_upsert(UserFavorite.__table__, values, ("user_id", "stock_code"))


def build_user_tag_upsert(document: dict[str, Any]):
    values = map_user_tag(document)
    return _build_upsert(UserTag.__table__, values, ("legacy_id",))


def build_paper_account_upsert(document: dict[str, Any]):
    values = map_paper_account(document)
    return _build_upsert(PaperAccount.__table__, values, ("user_id",))


def build_paper_position_upsert(document: dict[str, Any]):
    values = map_paper_position(document)
    return _build_upsert(PaperPosition.__table__, values, ("user_id", "code"))


def build_paper_order_upsert(document: dict[str, Any]):
    values = map_paper_order(document)
    return _build_upsert(PaperOrder.__table__, values, ("legacy_id",))


def build_paper_trade_upsert(document: dict[str, Any]):
    values = map_paper_trade(document)
    return _build_upsert(PaperTrade.__table__, values, ("legacy_id",))


def build_user_account_upsert(document: dict[str, Any]):
    values = map_user_account(document)
    return _build_upsert(UserAccount.__table__, values, ("username",))


def build_user_session_upsert(document: dict[str, Any]):
    values = map_user_session(document)
    return _build_upsert(UserSessionDocument.__table__, values, ("session_id",))


def build_login_attempt_upsert(document: dict[str, Any]):
    values = map_login_attempt(document)
    return _build_upsert(LoginAttemptDocument.__table__, values, ("legacy_id",))


def build_operation_log_upsert(document: dict[str, Any]):
    values = map_operation_log(document)
    return _build_upsert(OperationLogDocument.__table__, values, ("legacy_id",))


def build_database_backup_upsert(document: dict[str, Any]):
    values = map_database_backup(document)
    return _build_upsert(DatabaseBackupDocument.__table__, values, ("legacy_id",))


def build_notification_upsert(document: dict[str, Any]):
    values = map_notification(document)
    return _build_upsert(NotificationDocument.__table__, values, ("legacy_id",))


def build_token_usage_upsert(document: dict[str, Any]):
    values = map_token_usage(document)
    return _build_upsert(TokenUsageDocument.__table__, values, ("legacy_id",))


def build_internal_message_upsert(document: dict[str, Any]):
    values = map_internal_message(document)
    return _build_upsert(InternalMessageDocument.__table__, values, ("message_id",))


def build_social_media_message_upsert(document: dict[str, Any]):
    values = map_social_media_message(document)
    return _build_upsert(SocialMediaMessageDocument.__table__, values, ("message_id", "platform"))


async def upsert_stock_basic_info(session, document: dict[str, Any]) -> None:
    await session.execute(build_stock_basic_info_upsert(document))


async def upsert_market_quote(session, document: dict[str, Any]) -> None:
    await session.execute(build_market_quote_upsert(document))


async def upsert_stock_daily_quote(session, document: dict[str, Any]) -> None:
    await session.execute(build_stock_daily_quote_upsert(document))


async def upsert_stock_financial_data(session, document: dict[str, Any]) -> None:
    await session.execute(build_stock_financial_data_upsert(document))


async def upsert_stock_news(session, document: dict[str, Any]) -> None:
    await session.execute(build_stock_news_upsert(document))


async def upsert_analysis_task(session, document: dict[str, Any]) -> None:
    await session.execute(build_analysis_task_upsert(document))


async def upsert_analysis_report(session, document: dict[str, Any]) -> None:
    await session.execute(build_analysis_report_upsert(document))


async def upsert_analysis_batch(session, document: dict[str, Any]) -> None:
    await session.execute(build_analysis_batch_upsert(document))


async def upsert_analysis_result(session, document: dict[str, Any]) -> None:
    await session.execute(build_analysis_result_upsert(document))


async def upsert_sync_status(session, document: dict[str, Any]) -> None:
    await session.execute(build_sync_status_upsert(document))


async def upsert_scheduler_execution(session, document: dict[str, Any]) -> None:
    await session.execute(build_scheduler_execution_upsert(document))


async def upsert_scheduler_history(session, document: dict[str, Any]) -> None:
    await session.execute(build_scheduler_history_upsert(document))


async def upsert_scheduler_metadata(session, document: dict[str, Any]) -> None:
    await session.execute(build_scheduler_metadata_upsert(document))


async def upsert_system_config_document(
    session,
    document: dict[str, Any],
    *,
    collection: str = "system_configs",
) -> None:
    await session.execute(build_system_config_document_upsert(document, collection=collection))


async def upsert_user_favorite(session, document: dict[str, Any]) -> None:
    await session.execute(build_user_favorite_upsert(document))


async def upsert_user_tag(session, document: dict[str, Any]) -> None:
    await session.execute(build_user_tag_upsert(document))


async def upsert_paper_account(session, document: dict[str, Any]) -> None:
    await session.execute(build_paper_account_upsert(document))


async def upsert_paper_position(session, document: dict[str, Any]) -> None:
    await session.execute(build_paper_position_upsert(document))


async def upsert_paper_order(session, document: dict[str, Any]) -> None:
    await session.execute(build_paper_order_upsert(document))


async def upsert_paper_trade(session, document: dict[str, Any]) -> None:
    await session.execute(build_paper_trade_upsert(document))


async def upsert_user_account(session, document: dict[str, Any]) -> None:
    await session.execute(build_user_account_upsert(document))


async def upsert_user_session(session, document: dict[str, Any]) -> None:
    await session.execute(build_user_session_upsert(document))


async def upsert_login_attempt(session, document: dict[str, Any]) -> None:
    await session.execute(build_login_attempt_upsert(document))


async def upsert_operation_log(session, document: dict[str, Any]) -> None:
    await session.execute(build_operation_log_upsert(document))


async def upsert_database_backup(session, document: dict[str, Any]) -> None:
    await session.execute(build_database_backup_upsert(document))


async def upsert_notification(session, document: dict[str, Any]) -> None:
    await session.execute(build_notification_upsert(document))


async def upsert_token_usage(session, document: dict[str, Any]) -> None:
    await session.execute(build_token_usage_upsert(document))


async def upsert_internal_message(session, document: dict[str, Any]) -> None:
    await session.execute(build_internal_message_upsert(document))


async def upsert_social_media_message(session, document: dict[str, Any]) -> None:
    await session.execute(build_social_media_message_upsert(document))


def _build_upsert(table, values: dict[str, Any], conflict_columns: Iterable[str]):
    statement = insert(table).values(**values)
    update_values = {
        key: getattr(statement.excluded, key)
        for key in values
        if key not in {"id", "created_at"}
    }
    return statement.on_conflict_do_update(
        index_elements=list(conflict_columns),
        set_=update_values,
    )
