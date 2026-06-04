from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Select, func, select

from app.db.model import (
    AnalysisBatchDocument,
    AnalysisReport,
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
    SocialMediaMessageDocument,
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SyncStatusDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)

BusinessKey = tuple[str, ...]


@dataclass(frozen=True)
class HotCollectionSpec:
    collection: str
    model: Any
    postgres_columns: tuple[str, ...]
    document_key: Callable[[dict[str, Any]], Any]
    document_collections: tuple[str, ...] | None = None

    @property
    def source_collections(self) -> tuple[str, ...]:
        return self.document_collections or (self.collection,)


@dataclass
class CollectionConsistency:
    collection: str
    document_count: int
    postgres_count: int
    count_delta: int
    sampled_document_keys: int
    sampled_postgres_keys: int
    missing_in_postgres: list[BusinessKey]
    extra_in_postgres: list[BusinessKey]
    sample_limit: int

    @property
    def is_consistent(self) -> bool:
        return (
            self.count_delta == 0
            and not self.missing_in_postgres
            and not self.extra_in_postgres
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["is_consistent"] = self.is_consistent
        return data


HOT_COLLECTION_SPECS: tuple[HotCollectionSpec, ...] = (
    HotCollectionSpec(
        collection="stock_basic_info",
        model=StockBasicInfo,
        postgres_columns=("code", "source"),
        document_key=lambda doc: (
            str(doc.get("code") or doc.get("symbol") or ""),
            str(doc.get("source") or doc.get("data_source") or ""),
        ),
    ),
    HotCollectionSpec(
        collection="market_quotes",
        model=MarketQuote,
        postgres_columns=("code", "source"),
        document_key=lambda doc: (
            str(doc.get("code") or doc.get("symbol") or ""),
            str(doc.get("source") or doc.get("data_source") or ""),
        ),
    ),
    HotCollectionSpec(
        collection="stock_daily_quotes",
        model=StockDailyQuote,
        postgres_columns=("symbol", "trade_date", "data_source", "period"),
        document_key=lambda doc: (
            str(doc.get("symbol") or doc.get("code") or ""),
            _date_key(doc.get("trade_date")),
            str(doc.get("data_source") or doc.get("source") or ""),
            str(doc.get("period") or "daily"),
        ),
    ),
    HotCollectionSpec(
        collection="stock_financial_data",
        model=StockFinancialData,
        postgres_columns=("code", "data_source", "report_period"),
        document_key=lambda doc: (
            str(doc.get("code") or doc.get("symbol") or ""),
            str(doc.get("data_source") or doc.get("source") or ""),
            str(doc.get("report_period") or ""),
        ),
    ),
    HotCollectionSpec(
        collection="stock_news",
        model=StockNewsDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (
            str(doc.get("_id") or doc.get("legacy_id") or _stock_news_legacy_id(doc)),
        ),
    ),
    HotCollectionSpec(
        collection="analysis_tasks",
        model=AnalysisTask,
        postgres_columns=("task_id",),
        document_key=lambda doc: (str(doc.get("task_id") or doc.get("id") or ""),),
    ),
    HotCollectionSpec(
        collection="analysis_reports",
        model=AnalysisReport,
        postgres_columns=("analysis_id",),
        document_key=lambda doc: (
            str(doc.get("analysis_id") or doc.get("task_id") or doc.get("id") or ""),
        ),
    ),
    HotCollectionSpec(
        collection="analysis_batches",
        model=AnalysisBatchDocument,
        postgres_columns=("batch_id",),
        document_key=lambda doc: (str(doc.get("batch_id") or doc.get("id") or ""),),
    ),
    HotCollectionSpec(
        collection="analysis_results",
        model=AnalysisResultDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (
            str(
                doc.get("_id")
                or doc.get("legacy_id")
                or _analysis_result_legacy_id(doc)
            ),
        ),
    ),
    HotCollectionSpec(
        collection="sync_status",
        model=SyncStatusDocument,
        postgres_columns=("job",),
        document_key=lambda doc: (
            str(doc.get("job") or doc.get("job_id") or doc.get("name") or ""),
        ),
        document_collections=("sync_status", "quotes_ingestion_status"),
    ),
    HotCollectionSpec(
        collection="scheduler_executions",
        model=SchedulerExecution,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="scheduler_history",
        model=SchedulerHistoryDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (
            str(
                doc.get("_id")
                or doc.get("legacy_id")
                or _scheduler_history_legacy_id(doc)
            ),
        ),
    ),
    HotCollectionSpec(
        collection="scheduler_metadata",
        model=SchedulerMetadataDocument,
        postgres_columns=("job_id",),
        document_key=lambda doc: (str(doc.get("job_id") or doc.get("job") or ""),),
    ),
    HotCollectionSpec(
        collection="user_favorites",
        model=UserFavorite,
        postgres_columns=("user_id", "stock_code"),
        document_key=lambda doc: _favorite_keys(doc),
    ),
    HotCollectionSpec(
        collection="user_tags",
        model=UserTag,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="paper_accounts",
        model=PaperAccount,
        postgres_columns=("user_id",),
        document_key=lambda doc: (str(doc.get("user_id") or ""),),
    ),
    HotCollectionSpec(
        collection="paper_positions",
        model=PaperPosition,
        postgres_columns=("user_id", "code"),
        document_key=lambda doc: (
            str(doc.get("user_id") or ""),
            str(doc.get("code") or ""),
        ),
    ),
    HotCollectionSpec(
        collection="paper_orders",
        model=PaperOrder,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="paper_trades",
        model=PaperTrade,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="users",
        model=UserAccount,
        postgres_columns=("username",),
        document_key=lambda doc: (str(doc.get("username") or ""),),
        document_collections=("users", "users_collection"),
    ),
    HotCollectionSpec(
        collection="user_sessions",
        model=UserSessionDocument,
        postgres_columns=("session_id",),
        document_key=lambda doc: (
            str(
                doc.get("session_id")
                or doc.get("token_id")
                or doc.get("jti")
                or _user_session_id(doc)
            ),
        ),
    ),
    HotCollectionSpec(
        collection="login_attempts",
        model=LoginAttemptDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (
            str(
                doc.get("_id") or doc.get("legacy_id") or _login_attempt_legacy_id(doc)
            ),
        ),
    ),
    HotCollectionSpec(
        collection="operation_logs",
        model=OperationLogDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="database_backups",
        model=DatabaseBackupDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="notifications",
        model=NotificationDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (str(doc.get("_id") or doc.get("legacy_id") or ""),),
    ),
    HotCollectionSpec(
        collection="token_usage",
        model=TokenUsageDocument,
        postgres_columns=("legacy_id",),
        document_key=lambda doc: (
            str(doc.get("_id") or doc.get("legacy_id") or _token_usage_legacy_id(doc)),
        ),
    ),
    HotCollectionSpec(
        collection="internal_messages",
        model=InternalMessageDocument,
        postgres_columns=("message_id",),
        document_key=lambda doc: (str(doc.get("message_id") or ""),),
    ),
    HotCollectionSpec(
        collection="social_media_messages",
        model=SocialMediaMessageDocument,
        postgres_columns=("message_id", "platform"),
        document_key=lambda doc: (
            str(doc.get("message_id") or ""),
            str(doc.get("platform") or ""),
        ),
    ),
)


async def compare_hot_collections(
    postgres_db,
    session_factory,
    sample_limit: int = 500,
) -> dict[str, CollectionConsistency]:
    results: dict[str, CollectionConsistency] = {}

    async with session_factory() as session:
        for spec in HOT_COLLECTION_SPECS:
            document_count = await _document_count(postgres_db, spec)
            table_count = await _table_count(session, spec.model)
            document_keys = await _document_business_keys(
                postgres_db, spec, sample_limit
            )
            table_keys = await _table_business_keys(session, spec, sample_limit)

            results[spec.collection] = CollectionConsistency(
                collection=spec.collection,
                document_count=document_count,
                postgres_count=table_count,
                count_delta=table_count - document_count,
                sampled_document_keys=len(document_keys),
                sampled_postgres_keys=len(table_keys),
                missing_in_postgres=sorted(document_keys - table_keys),
                extra_in_postgres=sorted(table_keys - document_keys),
                sample_limit=sample_limit,
            )

    return results


def consistency_summary_to_dict(
    results: dict[str, CollectionConsistency],
) -> dict[str, Any]:
    return {
        "all_consistent": all(result.is_consistent for result in results.values()),
        "collections": {name: result.to_dict() for name, result in results.items()},
    }


async def _table_count(session, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def _table_business_keys(
    session, spec: HotCollectionSpec, sample_limit: int
) -> set[BusinessKey]:
    columns = [
        getattr(spec.model, column_name) for column_name in spec.postgres_columns
    ]
    statement: Select = select(*columns).order_by(*columns).limit(sample_limit)
    result = await session.execute(statement)
    return {
        tuple("" if value is None else str(value) for value in row)
        for row in result.all()
    }


async def _document_count(postgres_db, spec: HotCollectionSpec) -> int:
    total = 0
    for collection_name in spec.source_collections:
        total += await postgres_db[collection_name].count_documents({})
    return total


async def _document_business_keys(
    postgres_db, spec: HotCollectionSpec, sample_limit: int
) -> set[BusinessKey]:
    keys: set[BusinessKey] = set()
    for collection_name in spec.source_collections:
        remaining = max(sample_limit - len(keys), 0)
        if remaining <= 0:
            break
        cursor = postgres_db[collection_name].find({}).limit(remaining)
        async for document in cursor:
            for key in _iter_business_keys(spec.document_key(document)):
                if all(key):
                    keys.add(key)
    return keys


def _iter_business_keys(value) -> set[BusinessKey]:
    if isinstance(value, set):
        return value
    if isinstance(value, list | tuple) and value and isinstance(value[0], tuple):
        return set(value)
    if isinstance(value, tuple):
        return {value}
    return set()


def _favorite_keys(document: dict[str, Any]) -> set[BusinessKey]:
    user_id = str(document.get("user_id") or "")
    if document.get("stock_code"):
        return {(user_id, str(document.get("stock_code") or ""))}
    return {
        (user_id, str(favorite.get("stock_code") or ""))
        for favorite in document.get("favorites") or []
        if isinstance(favorite, dict)
    }


def _stock_news_legacy_id(document: dict[str, Any]) -> str:
    map_stock_news = getattr(
        importlib.import_module("app.db.document"), "map_stock_news"
    )

    return str(map_stock_news(document)["legacy_id"])


def _scheduler_history_legacy_id(document: dict[str, Any]) -> str:
    map_scheduler_history = getattr(
        importlib.import_module("app.db.document"), "map_scheduler_history"
    )

    return str(map_scheduler_history(document)["legacy_id"])


def _analysis_result_legacy_id(document: dict[str, Any]) -> str:
    map_analysis_result = getattr(
        importlib.import_module("app.db.document"), "map_analysis_result"
    )

    return str(map_analysis_result(document)["legacy_id"])


def _token_usage_legacy_id(document: dict[str, Any]) -> str:
    map_token_usage = getattr(
        importlib.import_module("app.db.document"), "map_token_usage"
    )

    return str(map_token_usage(document)["legacy_id"])


def _user_session_id(document: dict[str, Any]) -> str:
    map_user_session = getattr(
        importlib.import_module("app.db.document"), "map_user_session"
    )

    return str(map_user_session(document)["session_id"])


def _login_attempt_legacy_id(document: dict[str, Any]) -> str:
    map_login_attempt = getattr(
        importlib.import_module("app.db.document"), "map_login_attempt"
    )

    return str(map_login_attempt(document)["legacy_id"])


def _date_key(value: Any) -> str:
    map_stock_daily_quote = getattr(
        importlib.import_module("app.db.document"), "map_stock_daily_quote"
    )

    mapped = map_stock_daily_quote(
        {"symbol": "x", "trade_date": value, "data_source": "x"}
    )
    trade_date = mapped["trade_date"]
    return trade_date.isoformat() if trade_date else ""
