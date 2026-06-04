# ruff: noqa: F401,F403,F405,F821
from __future__ import annotations

import asyncio
import atexit
import copy
import importlib
import re
import threading
import uuid
from collections.abc import Coroutine
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.session import get_session_factory, init_postgres
from app.db.document import normalize_payload
from app.models.table import PostgresDocument, SystemConfigDocument

from .imports import CONFIG_COLLECTIONS, SPECIALIZED_MODELS

_sync_loop: asyncio.AbstractEventLoop | None = None
_sync_loop_thread: threading.Thread | None = None
_sync_loop_lock = threading.Lock()


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
        await getattr(
            importlib.import_module("app.db.dual"), "dual_write_hot_document"
        )(collection, document, enabled=True, fail_open=True)
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
