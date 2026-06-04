from __future__ import annotations

import asyncio
import atexit
import copy
import re
import threading
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Self, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.document import normalize_payload
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
    PostgresDocument,
    SchedulerExecution,
    SchedulerHistoryDocument,
    SchedulerMetadataDocument,
    SocialMediaMessageDocument,
    StockBasicInfo,
    StockDailyQuote,
    StockFinancialData,
    StockNewsDocument,
    SyncStatusDocument,
    SystemConfigDocument,
    TokenUsageDocument,
    UserAccount,
    UserFavorite,
    UserSessionDocument,
    UserTag,
)
from app.db.session import get_session_factory, init_postgres

_sync_loop: asyncio.AbstractEventLoop | None = None
_sync_loop_thread: threading.Thread | None = None
_sync_loop_lock = threading.Lock()


SPECIALIZED_MODELS: dict[str, Any] = {
    "stock_basic_info": StockBasicInfo,
    "market_quotes": MarketQuote,
    "stock_daily_quotes": StockDailyQuote,
    "stock_financial_data": StockFinancialData,
    "stock_news": StockNewsDocument,
    "analysis_tasks": AnalysisTask,
    "analysis_reports": AnalysisReport,
    "analysis_batches": AnalysisBatchDocument,
    "analysis_results": AnalysisResultDocument,
    "sync_status": SyncStatusDocument,
    "quotes_ingestion_status": SyncStatusDocument,
    "scheduler_executions": SchedulerExecution,
    "scheduler_history": SchedulerHistoryDocument,
    "scheduler_metadata": SchedulerMetadataDocument,
    "user_favorites": UserFavorite,
    "user_tags": UserTag,
    "paper_accounts": PaperAccount,
    "paper_positions": PaperPosition,
    "paper_orders": PaperOrder,
    "paper_trades": PaperTrade,
    "users": UserAccount,
    "users_collection": UserAccount,
    "user_sessions": UserSessionDocument,
    "login_attempts": LoginAttemptDocument,
    "operation_logs": OperationLogDocument,
    "database_backups": DatabaseBackupDocument,
    "notifications": NotificationDocument,
    "token_usage": TokenUsageDocument,
    "internal_messages": InternalMessageDocument,
    "social_media_messages": SocialMediaMessageDocument,
}

CONFIG_COLLECTIONS = {
    "system_configs",
    "llm_providers",
    "model_catalog",
    "market_categories",
    "datasource_groupings",
}


@dataclass(frozen=True)
class InsertOneResult:
    inserted_id: Any
    acknowledged: bool = True


@dataclass(frozen=True)
class InsertManyResult:
    inserted_ids: list[Any]
    acknowledged: bool = True


@dataclass(frozen=True)
class UpdateResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: Any = None
    acknowledged: bool = True


@dataclass(frozen=True)
class DeleteResult:
    deleted_count: int = 0
    acknowledged: bool = True


@dataclass(frozen=True)
class BulkWriteResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_ids: dict[int, Any] = field(default_factory=dict)

    @property
    def upserted_count(self) -> int:
        return len(self.upserted_ids)


class BulkWriteError(Exception):
    """PostgreSQL document-store bulk write error."""

    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__(details or {})
        self.details = details or {}


class UpdateOne:
    def __init__(
        self,
        filter: dict[str, Any],
        update: dict[str, Any] | None = None,
        *,
        upsert: bool = False,
        **kwargs: Any,
    ):
        self._filter = filter
        self._doc = update if update is not None else kwargs.get("doc", {})
        self._upsert = upsert


class ReplaceOne:
    def __init__(
        self,
        filter: dict[str, Any] | None = None,
        replacement: dict[str, Any] | None = None,
        *,
        upsert: bool = False,
        **kwargs: Any,
    ):
        self._filter = filter if filter is not None else kwargs.get("filter", {})
        self._doc = (
            replacement
            if replacement is not None
            else kwargs.get("replacement", kwargs.get("doc", {}))
        )
        self._upsert = upsert


class InsertOne:
    def __init__(self, document: dict[str, Any] | None = None, **kwargs: Any):
        self._doc = (
            document
            if document is not None
            else kwargs.get("document", kwargs.get("doc", {}))
        )


class DeleteOne:
    def __init__(self, filter: dict[str, Any] | None = None, **kwargs: Any):
        self._filter = filter if filter is not None else kwargs.get("filter", {})


class DeleteMany:
    def __init__(self, filter: dict[str, Any] | None = None, **kwargs: Any):
        self._filter = filter if filter is not None else kwargs.get("filter", {})


class PostgresCursor:
    def __init__(
        self,
        documents: list[dict[str, Any]] | None = None,
        loader: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
    ):
        self._documents = documents
        self._loader = loader
        self._skip = 0
        self._limit: int | None = None
        self._index = 0
        self._sort_items: list[tuple[str, int]] = []

    def sort(self, key_or_list: Any, direction: int | None = None) -> Self:
        self._sort_items.extend(_normalize_sort(key_or_list, direction))
        return self

    def skip(self, count: int) -> Self:
        self._skip = max(count, 0)
        return self

    def limit(self, count: int | None) -> Self:
        self._limit = count if count and count > 0 else None
        return self

    def batch_size(self, _size: int) -> Self:
        return self

    def close(self) -> None:
        return None

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        items = await self._window()
        if length is not None:
            return items[:length]
        return items

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(cast(list[dict[str, Any]], _run_blocking(self._window())))

    def __aiter__(self) -> Self:
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        items = await self._window()
        if self._index >= len(items):
            raise StopAsyncIteration
        item = items[self._index]
        self._index += 1
        return item

    async def _ensure_loaded(self) -> list[dict[str, Any]]:
        if self._documents is None:
            self._documents = await self._loader() if self._loader is not None else []
            for key, sort_direction in reversed(self._sort_items):
                self._documents.sort(
                    key=lambda document: _sort_key(_get_value(document, key)),
                    reverse=sort_direction < 0,
                )
        return self._documents

    async def _window(self) -> list[dict[str, Any]]:
        documents = await self._ensure_loaded()
        items = documents[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return [copy.deepcopy(item) for item in items]


class PostgresCollection:
    def __init__(self, name: str):
        self.name = name

    async def find_one(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any] | None:
        cursor = self.find(query, projection)
        if sort := kwargs.get("sort"):
            cursor.sort(sort)
        rows = await cursor.limit(1).to_list(1)
        return rows[0] if rows else None

    def find(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
        *_,
        **__,
    ) -> PostgresCursor:
        async def load() -> list[dict[str, Any]]:
            documents = await self._load_documents()
            return [
                _project(document, projection)
                for document in documents
                if _matches(document, query or {})
            ]

        return PostgresCursor(loader=load)

    async def count_documents(self, query: dict[str, Any] | None = None) -> int:
        cursor = self.find(query)
        return len(await cursor.to_list(None))

    async def estimated_document_count(self) -> int:
        return await self.count_documents({})

    async def distinct(
        self, key: str, query: dict[str, Any] | None = None
    ) -> list[Any]:
        cursor = self.find(query)
        rows = await cursor.to_list(None)
        values: list[Any] = []
        for row in rows:
            value = _get_value(row, key)
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if candidate is not None and candidate not in values:
                    values.append(candidate)
        return values

    async def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        document = _ensure_document_id(document)
        await self._save_document(document)
        return InsertOneResult(document["_id"])

    async def insert_many(
        self, documents: Iterable[dict[str, Any]]
    ) -> InsertManyResult:
        inserted: list[Any] = []
        for document in documents:
            result = await self.insert_one(document)
            inserted.append(result.inserted_id)
        return InsertManyResult(inserted)

    async def replace_one(
        self,
        query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
        **__,
    ) -> UpdateResult:
        existing = await self.find_one(query)
        if existing is None and not upsert:
            return UpdateResult()

        document_id = (
            existing.get("_id") if existing else _document_id_from_filter(query)
        )
        document = {
            **replacement,
            "_id": document_id or replacement.get("_id") or _new_document_id(),
        }
        await self._save_document(document)
        return UpdateResult(
            matched_count=1 if existing else 0,
            modified_count=1,
            upserted_id=None if existing else document["_id"],
        )

    async def update_one(
        self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False, **__
    ) -> UpdateResult:
        existing = await self.find_one(query)
        if existing is None:
            if not upsert:
                return UpdateResult()
            existing = {"_id": _document_id_from_filter(query) or _new_document_id()}
            _merge_filter_identity(existing, query)
            upserted_id = existing["_id"]
        else:
            upserted_id = None

        updated = _apply_update(existing, update, is_insert=upserted_id is not None)
        await self._save_document(updated)
        return UpdateResult(
            matched_count=0 if upserted_id is not None else 1,
            modified_count=1,
            upserted_id=upserted_id,
        )

    async def update_many(
        self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False, **__
    ) -> UpdateResult:
        cursor = self.find(query)
        rows = await cursor.to_list(None)
        if not rows and upsert:
            return await self.update_one(query, update, upsert=True)

        modified = 0
        for row in rows:
            await self._save_document(_apply_update(row, update, is_insert=False))
            modified += 1
        return UpdateResult(matched_count=len(rows), modified_count=modified)

    async def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        documents = self.find(query)
        rows = await documents.limit(1).to_list(1)
        if not rows:
            return DeleteResult(0)
        await self._delete_documents([rows[0]])
        return DeleteResult(1)

    async def delete_many(self, query: dict[str, Any]) -> DeleteResult:
        cursor = self.find(query)
        rows = await cursor.to_list(None)
        await self._delete_documents(rows)
        return DeleteResult(len(rows))

    async def bulk_write(
        self, operations: Iterable[Any], ordered: bool = True
    ) -> BulkWriteResult:
        matched = 0
        modified = 0
        upserted: dict[int, Any] = {}
        for index, operation in enumerate(operations):
            try:
                name = type(operation).__name__
                if name == "UpdateOne":
                    result = await self.update_one(
                        operation._filter,
                        operation._doc,
                        upsert=bool(operation._upsert),
                    )
                    matched += result.matched_count
                    modified += result.modified_count
                    if result.upserted_id is not None:
                        upserted[index] = result.upserted_id
                elif name == "ReplaceOne":
                    result = await self.replace_one(
                        operation._filter,
                        operation._doc,
                        upsert=bool(operation._upsert),
                    )
                    matched += result.matched_count
                    modified += result.modified_count
                    if result.upserted_id is not None:
                        upserted[index] = result.upserted_id
                elif name == "InsertOne":
                    await self.insert_one(operation._doc)
                    upserted[index] = operation._doc.get("_id")
                elif name == "DeleteOne":
                    result = await self.delete_one(operation._filter)
                    modified += result.deleted_count
                elif name == "DeleteMany":
                    result = await self.delete_many(operation._filter)
                    modified += result.deleted_count
            except Exception:
                if ordered:
                    raise
        return BulkWriteResult(
            matched_count=matched, modified_count=modified, upserted_ids=upserted
        )

    def aggregate(self, pipeline: list[dict[str, Any]], *_, **__) -> PostgresCursor:
        async def load() -> list[dict[str, Any]]:
            documents = await self._load_documents()
            for stage in pipeline:
                if "$match" in stage:
                    documents = [
                        document
                        for document in documents
                        if _matches(document, stage["$match"])
                    ]
                elif "$sort" in stage:
                    cursor = PostgresCursor(documents).sort(
                        list(stage["$sort"].items())
                    )
                    documents = await cursor.to_list(None)
                elif "$skip" in stage:
                    documents = documents[int(stage["$skip"]) :]
                elif "$limit" in stage:
                    documents = documents[: int(stage["$limit"])]
                elif "$project" in stage:
                    documents = [
                        _project(document, stage["$project"]) for document in documents
                    ]
                elif "$count" in stage:
                    documents = [{stage["$count"]: len(documents)}]
                elif "$group" in stage:
                    documents = _group_documents(documents, stage["$group"])
            return documents

        return PostgresCursor(loader=load)

    async def create_index(self, *_, **__) -> str:
        return "postgres_document_index"

    async def drop(self) -> None:
        await self.delete_many({})

    async def _load_documents(self) -> list[dict[str, Any]]:
        await _ensure_postgres()
        factory = get_session_factory()
        async with factory() as session:
            generic_rows = (
                (
                    await session.execute(
                        select(PostgresDocument).where(
                            PostgresDocument.collection == self.name
                        )
                    )
                )
                .scalars()
                .all()
            )
            documents = [_row_to_document(row) for row in generic_rows]

            model = _model_for_collection(self.name)
            if model is not None:
                rows = (
                    (await session.execute(_build_specialized_select(self.name, model)))
                    .scalars()
                    .all()
                )
                seen = {str(document.get("_id")) for document in documents}
                for row in rows:
                    document = _row_to_document(row)
                    if self.name in CONFIG_COLLECTIONS and document.get(
                        "collection"
                    ) not in (self.name, None):
                        continue
                    if str(document.get("_id")) not in seen:
                        documents.append(document)
            return documents

    async def _save_document(self, document: dict[str, Any]) -> None:
        await _ensure_postgres()
        document = normalize_payload(_ensure_document_id(document))
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(build_document_upsert(self.name, document))
            await session.commit()

        await _write_specialized_table(self.name, document)

    async def _delete_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        await _ensure_postgres()
        document_ids = [str(document.get("_id")) for document in documents]
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                delete(PostgresDocument).where(
                    PostgresDocument.collection == self.name,
                    PostgresDocument.document_id.in_(document_ids),
                )
            )
            await session.commit()


class SyncPostgresCollection:
    def __init__(self, async_collection: PostgresCollection):
        self._async = async_collection

    def find_one(self, *args, **kwargs) -> Any:
        return _run_blocking(self._async.find_one(*args, **kwargs))

    def find(self, *args, **kwargs) -> PostgresCursor:
        return self._async.find(*args, **kwargs)

    def count_documents(self, *args, **kwargs) -> int:
        return _run_blocking(self._async.count_documents(*args, **kwargs))

    def estimated_document_count(self, *args, **kwargs) -> int:
        return _run_blocking(self._async.estimated_document_count(*args, **kwargs))

    def insert_one(self, *args, **kwargs) -> InsertOneResult:
        return _run_blocking(self._async.insert_one(*args, **kwargs))

    def insert_many(self, *args, **kwargs) -> InsertManyResult:
        return _run_blocking(self._async.insert_many(*args, **kwargs))

    def update_one(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.update_one(*args, **kwargs))

    def update_many(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.update_many(*args, **kwargs))

    def replace_one(self, *args, **kwargs) -> UpdateResult:
        return _run_blocking(self._async.replace_one(*args, **kwargs))

    def delete_one(self, *args, **kwargs) -> DeleteResult:
        return _run_blocking(self._async.delete_one(*args, **kwargs))

    def delete_many(self, *args, **kwargs) -> DeleteResult:
        return _run_blocking(self._async.delete_many(*args, **kwargs))

    def bulk_write(self, *args, **kwargs) -> BulkWriteResult:
        return _run_blocking(self._async.bulk_write(*args, **kwargs))

    def aggregate(self, *args, **kwargs) -> PostgresCursor:
        return self._async.aggregate(*args, **kwargs)

    def distinct(self, *args, **kwargs) -> list[Any]:
        return _run_blocking(self._async.distinct(*args, **kwargs))

    def create_index(self, *args, **kwargs) -> str:
        return _run_blocking(self._async.create_index(*args, **kwargs))

    def drop(self) -> Any:
        return _run_blocking(self._async.drop())


class PostgresDocumentDatabase:
    def __getitem__(self, collection: str) -> PostgresCollection:
        return PostgresCollection(collection)

    def __getattr__(self, collection: str) -> PostgresCollection:
        if collection.startswith("_"):
            raise AttributeError(collection)
        return self[collection]

    async def list_collection_names(self) -> list[str]:
        await _ensure_postgres()
        factory = get_session_factory()
        async with factory() as session:
            generic = (
                (await session.execute(select(PostgresDocument.collection).distinct()))
                .scalars()
                .all()
            )
        return sorted(set(generic) | set(SPECIALIZED_MODELS) | CONFIG_COLLECTIONS)

    async def command(self, *_args, **_kwargs) -> dict[str, int]:
        return {"ok": 1}


class SyncPostgresDocumentDatabase:
    def __getitem__(self, collection: str) -> SyncPostgresCollection:
        return SyncPostgresCollection(PostgresCollection(collection))

    def __getattr__(self, collection: str) -> SyncPostgresCollection:
        if collection.startswith("_"):
            raise AttributeError(collection)
        return self[collection]

    def list_collection_names(self) -> list[str]:
        return cast(
            list[str], _run_blocking(PostgresDocumentDatabase().list_collection_names())
        )

    def command(self, *_args, **_kwargs) -> dict[str, int]:
        return {"ok": 1}


class PostgresDocumentClient:
    @property
    def admin(self) -> Self:
        return self

    async def command(self, *_args, **_kwargs) -> dict[str, int]:
        return {"ok": 1}

    def close(self) -> None:
        return None

    def __getitem__(self, _database: str) -> PostgresDocumentDatabase:
        return PostgresDocumentDatabase()


class SyncPostgresDocumentClient:
    @property
    def admin(self) -> Self:
        return self

    def command(self, *_args, **_kwargs) -> dict[str, int]:
        return {"ok": 1}

    def close(self) -> None:
        return None

    def get_database(
        self, _database: str | None = None
    ) -> SyncPostgresDocumentDatabase:
        return SyncPostgresDocumentDatabase()

    def __getitem__(self, _database: str) -> SyncPostgresDocumentDatabase:
        return SyncPostgresDocumentDatabase()

    def __getattr__(self, database: str) -> SyncPostgresDocumentDatabase:
        if database.startswith("_"):
            raise AttributeError(database)
        return SyncPostgresDocumentDatabase()


def create_database() -> PostgresDocumentDatabase:
    return PostgresDocumentDatabase()


def create_sync_database() -> SyncPostgresDocumentDatabase:
    return SyncPostgresDocumentDatabase()


def create_client() -> PostgresDocumentClient:
    return PostgresDocumentClient()


def create_sync_client() -> SyncPostgresDocumentClient:
    return SyncPostgresDocumentClient()


def build_document_upsert(collection: str, document: dict[str, Any]):
    document = normalize_payload(_ensure_document_id(document))
    now = datetime.now(timezone.utc)
    statement = insert(PostgresDocument).values(
        collection=collection,
        document_id=str(document["_id"]),
        payload=document,
        updated_at=now,
    )
    return statement.on_conflict_do_update(
        index_elements=[PostgresDocument.collection, PostgresDocument.document_id],
        set_={"payload": document, "updated_at": now},
    )


async def _ensure_postgres() -> None:
    try:
        get_session_factory()
    except RuntimeError:
        await init_postgres()


async def _write_specialized_table(collection: str, document: dict[str, Any]) -> None:
    if _model_for_collection(collection) is None:
        return
    try:
        from app.db.dual import dual_write_hot_document

        await dual_write_hot_document(
            collection, document, enabled=True, fail_open=True
        )
    except Exception:
        return


def _model_for_collection(collection: str) -> Any | None:
    if collection in CONFIG_COLLECTIONS:
        return SystemConfigDocument
    return SPECIALIZED_MODELS.get(collection)


def _build_specialized_select(collection: str, model: Any):
    statement = select(model)
    if collection in CONFIG_COLLECTIONS:
        return statement.where(model.config_type == collection)
    return statement


def _row_to_document(row: Any) -> dict[str, Any]:
    payload = copy.deepcopy(row.payload or {})
    if "_id" not in payload:
        payload["_id"] = (
            getattr(row, "legacy_id", None)
            or getattr(row, "document_id", None)
            or str(getattr(row, "id", ""))
        )
    return payload


def _ensure_document_id(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    if result.get("_id") is None:
        result["_id"] = _new_document_id()
    return result


def _new_document_id() -> str:
    return uuid.uuid4().hex[:24]


def _document_id_from_filter(query: dict[str, Any]) -> Any:
    value = query.get("_id")
    if isinstance(value, dict):
        return None
    return value


def _merge_filter_identity(document: dict[str, Any], query: dict[str, Any]) -> None:
    for key, value in query.items():
        if key.startswith("$") or isinstance(value, dict):
            continue
        _set_value(document, key, value)


def _apply_update(
    document: dict[str, Any], update: dict[str, Any], *, is_insert: bool
) -> dict[str, Any]:
    result = copy.deepcopy(document)
    if not update:
        return result
    if not any(key.startswith("$") for key in update):
        replacement = copy.deepcopy(update)
        replacement.setdefault("_id", result.get("_id"))
        return replacement

    for key, value in update.get("$set", {}).items():
        _set_value(result, key, value)
    if is_insert:
        for key, value in update.get("$setOnInsert", {}).items():
            _set_value(result, key, value)
    for key in update.get("$unset", {}):
        _unset_value(result, key)
    for key, value in update.get("$inc", {}).items():
        current = _get_value(result, key) or 0
        _set_value(result, key, current + value)
    for key, value in update.get("$push", {}).items():
        current = _get_value(result, key) or []
        if not isinstance(current, list):
            current = [current]
        if isinstance(value, dict) and "$each" in value:
            current.extend(value["$each"])
        else:
            current.append(value)
        _set_value(result, key, current)
    for key, value in update.get("$addToSet", {}).items():
        current = _get_value(result, key) or []
        if not isinstance(current, list):
            current = [current]
        values = (
            value.get("$each", [])
            if isinstance(value, dict) and "$each" in value
            else [value]
        )
        for item in values:
            if item not in current:
                current.append(item)
        _set_value(result, key, current)
    for key, value in update.get("$pull", {}).items():
        current = _get_value(result, key) or []
        if isinstance(current, list):
            _set_value(
                result,
                key,
                [item for item in current if not _matches_value(item, value)],
            )
    return result


def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if key == "$and":
            if not all(_matches(document, item) for item in expected):
                return False
            continue
        if key == "$or":
            if not any(_matches(document, item) for item in expected):
                return False
            continue
        if key == "$expr":
            continue
        actual = _get_value(document, key)
        if not _matches_value(actual, expected):
            return False
    return True


def _matches_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        for operator, value in expected.items():
            if operator == "$in":
                if _normalize_compare(actual) not in {
                    _normalize_compare(item) for item in value
                }:
                    return False
            elif operator == "$nin":
                if _normalize_compare(actual) in {
                    _normalize_compare(item) for item in value
                }:
                    return False
            elif operator == "$ne":
                if _equal(actual, value):
                    return False
            elif operator == "$lt":
                if not (_comparable(actual) < _comparable(value)):
                    return False
            elif operator == "$lte":
                if not (_comparable(actual) <= _comparable(value)):
                    return False
            elif operator == "$gt":
                if not (_comparable(actual) > _comparable(value)):
                    return False
            elif operator == "$gte":
                if not (_comparable(actual) >= _comparable(value)):
                    return False
            elif operator == "$exists":
                if (actual is not None) is not bool(value):
                    return False
            elif operator == "$regex":
                flags = re.IGNORECASE if expected.get("$options") == "i" else 0
                if actual is None or re.search(str(value), str(actual), flags) is None:
                    return False
            elif operator == "$options":
                continue
            else:
                if not _equal(actual, expected):
                    return False
        return True
    if isinstance(actual, list):
        return any(_equal(item, expected) for item in actual)
    return _equal(actual, expected)


def _equal(left: Any, right: Any) -> bool:
    return _normalize_compare(left) == _normalize_compare(right)


def _normalize_compare(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return (
        str(value)
        if value is not None and type(value).__module__.startswith("app.db.ids")
        else value
    )


def _comparable(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _get_value(document: dict[str, Any], dotted_key: str) -> Any:
    current: Any = document
    for part in dotted_key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _set_value(document: dict[str, Any], dotted_key: str, value: Any) -> None:
    current = document
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _unset_value(document: dict[str, Any], dotted_key: str) -> None:
    current = document
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            return
        current = next_value
    current.pop(parts[-1], None)


def _project(
    document: dict[str, Any], projection: dict[str, Any] | None
) -> dict[str, Any]:
    if not projection:
        return copy.deepcopy(document)
    include_keys = {key for key, value in projection.items() if value}
    exclude_keys = {key for key, value in projection.items() if not value}
    if include_keys:
        projected = {}
        for key in include_keys:
            value = _get_value(document, key)
            if value is not None:
                _set_value(projected, key, value)
        if projection.get("_id", 1) and "_id" in document:
            projected["_id"] = document["_id"]
        return projected
    projected = copy.deepcopy(document)
    for key in exclude_keys:
        _unset_value(projected, key)
    return projected


def _normalize_sort(
    key_or_list: Any, direction: int | None = None
) -> list[tuple[str, int]]:
    if isinstance(key_or_list, str):
        return [(key_or_list, direction or 1)]
    if isinstance(key_or_list, dict):
        return [(str(key), int(value)) for key, value in key_or_list.items()]
    return [(str(key), int(value)) for key, value in key_or_list]


def _sort_key(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _group_documents(
    documents: list[dict[str, Any]], group: dict[str, Any]
) -> list[dict[str, Any]]:
    key_expr = group.get("_id")
    grouped: dict[Any, dict[str, Any]] = {}
    for document in documents:
        key = (
            _get_value(document, key_expr[1:])
            if isinstance(key_expr, str) and key_expr.startswith("$")
            else key_expr
        )
        bucket = grouped.setdefault(key, {"_id": key})
        for field_name, accumulator in group.items():
            if field_name == "_id":
                continue
            if isinstance(accumulator, dict) and "$sum" in accumulator:
                sum_value = accumulator["$sum"]
                bucket[field_name] = bucket.get(field_name, 0) + (
                    _get_value(document, sum_value[1:])
                    if isinstance(sum_value, str) and sum_value.startswith("$")
                    else sum_value
                )
    return list(grouped.values())


def _run_blocking(coro: Coroutine[Any, Any, Any]) -> Any:
    loop = _get_sync_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _get_sync_loop() -> asyncio.AbstractEventLoop:
    global _sync_loop, _sync_loop_thread

    with _sync_loop_lock:
        if _sync_loop is not None and _sync_loop.is_running():
            return _sync_loop

        ready = threading.Event()
        loop = asyncio.new_event_loop()

        def runner() -> None:
            asyncio.set_event_loop(loop)
            ready.set()
            loop.run_forever()

        thread = threading.Thread(
            target=runner, name="postgres-document-sync-loop", daemon=True
        )
        thread.start()
        ready.wait()
        _sync_loop = loop
        _sync_loop_thread = thread
        return loop


def close_sync_loop() -> None:
    global _sync_loop, _sync_loop_thread

    with _sync_loop_lock:
        loop = _sync_loop
        thread = _sync_loop_thread
        _sync_loop = None
        _sync_loop_thread = None

    if loop is not None and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=2)


atexit.register(close_sync_loop)
