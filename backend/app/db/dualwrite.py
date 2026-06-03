from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.coreconfig import settings
from app.db.mongotopostgresmigrator import HOT_COLLECTIONS
from app.db.session import get_session_factory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DualWriteResult:
    status: str
    collection: str
    reason: str = ""


@dataclass(frozen=True)
class DualWriteBatchResult:
    status: str
    collection: str
    attempted: int
    written: int
    reason: str = ""


def log_mongo_only_write(collection: str, reason: str) -> DualWriteResult:
    """Record an intentional Mongo-only write during the staged migration."""

    logger.warning("Mongo-only write retained during PostgreSQL migration: collection=%s reason=%s", collection, reason)
    return DualWriteResult(status="skipped", collection=collection, reason=reason)


async def dual_write_hot_document(
    collection: str,
    document: dict[str, Any],
    *,
    session_factory=None,
    enabled: bool | None = None,
    fail_open: bool | None = None,
) -> DualWriteResult:
    result = await dual_write_hot_documents(
        collection,
        [document],
        session_factory=session_factory,
        enabled=enabled,
        fail_open=fail_open,
    )
    if result.status == "written":
        return DualWriteResult(status="written", collection=collection)
    return DualWriteResult(status=result.status, collection=collection, reason=result.reason)


async def dual_write_hot_documents(
    collection: str,
    documents: list[dict[str, Any]],
    *,
    session_factory=None,
    enabled: bool | None = None,
    fail_open: bool | None = None,
) -> DualWriteBatchResult:
    effective_enabled = settings.POSTGRES_DUAL_WRITE_ENABLED if enabled is None else enabled
    statement_builder = HOT_COLLECTIONS.get(collection)
    if not effective_enabled:
        _log_dual_write_event(
            collection=collection,
            status="skipped",
            attempted=len(documents),
            written=0,
            legacy_ids=_fallback_legacy_ids(collection, documents),
            reason="disabled",
        )
        return DualWriteBatchResult(
            status="skipped",
            collection=collection,
            attempted=len(documents),
            written=0,
            reason="disabled",
        )

    if statement_builder is None:
        _log_dual_write_event(
            collection=collection,
            status="skipped",
            attempted=len(documents),
            written=0,
            legacy_ids=_fallback_legacy_ids(collection, documents),
            reason="unsupported_collection",
        )
        return DualWriteBatchResult(
            status="skipped",
            collection=collection,
            attempted=len(documents),
            written=0,
            reason="unsupported_collection",
        )

    effective_fail_open = settings.POSTGRES_DUAL_WRITE_FAIL_OPEN if fail_open is None else fail_open
    written = 0
    legacy_ids: list[str] = []
    statement_groups: list[list[Any]] = []

    try:
        for document in documents:
            statements = _statements_from_builder(statement_builder, document)
            statement_groups.append(statements)
            legacy_ids.extend(_legacy_ids_from_statements(statements))

        factory = session_factory or get_session_factory()
        async with factory() as session:
            for statements in statement_groups:
                for statement in statements:
                    await session.execute(statement)
                    written += 1
            await session.commit()
    except Exception as exc:
        legacy_ids = legacy_ids or _fallback_legacy_ids(collection, documents)
        _log_dual_write_event(
            collection=collection,
            status="failed",
            attempted=len(documents),
            written=written,
            legacy_ids=legacy_ids,
            reason=str(exc),
        )
        if effective_fail_open:
            return DualWriteBatchResult(
                status="failed",
                collection=collection,
                attempted=len(documents),
                written=written,
                reason=str(exc),
            )
        raise

    _log_dual_write_event(
        collection=collection,
        status="written",
        attempted=len(documents),
        written=written,
        legacy_ids=legacy_ids,
    )
    return DualWriteBatchResult(
        status="written",
        collection=collection,
        attempted=len(documents),
        written=written,
    )


def _statements_from_builder(statement_builder, document: dict[str, Any]) -> list[Any]:
    statements = statement_builder(document)
    if isinstance(statements, list | tuple):
        return list(statements)
    return [statements]


def _legacy_ids_from_statements(statements: list[Any]) -> list[str]:
    legacy_ids: list[str] = []
    for statement in statements:
        value_map = getattr(statement, "_values", {})
        raw_legacy_id = value_map.get("legacy_id")
        legacy_id = getattr(raw_legacy_id, "value", raw_legacy_id)
        if legacy_id is not None:
            legacy_ids.append(str(legacy_id))
    return legacy_ids


def _fallback_legacy_ids(collection: str, documents: list[dict[str, Any]]) -> list[str]:
    legacy_ids: list[str] = []
    for document in documents:
        if document.get("legacy_id") is not None:
            legacy_ids.append(str(document["legacy_id"]))
            continue
        if document.get("_id") is not None:
            legacy_ids.append(str(document["_id"]))
            continue
        key_parts = [
            document.get("task_id"),
            document.get("analysis_id"),
            document.get("batch_id"),
            document.get("message_id"),
            document.get("session_id"),
            document.get("job"),
            document.get("job_id"),
            document.get("username"),
            document.get("user_id"),
            document.get("code") or document.get("symbol"),
            document.get("source") or document.get("data_source"),
            document.get("trade_date"),
        ]
        key = ":".join(str(part) for part in key_parts if part not in (None, ""))
        legacy_ids.append(f"{collection}:{key}" if key else f"{collection}:unknown")
    return legacy_ids


def _log_dual_write_event(
    *,
    collection: str,
    status: str,
    attempted: int,
    written: int,
    legacy_ids: list[str],
    reason: str = "",
) -> None:
    legacy_id_text = _format_legacy_ids(legacy_ids)
    message = (
        "PostgreSQL dual-write collection=%s status=%s attempted=%s "
        "written=%s legacy_ids=%s reason=%s"
    )
    args = (collection, status, attempted, written, legacy_id_text, reason)
    if status == "failed":
        logger.warning(message, *args)
    elif status == "written":
        logger.info(message, *args)
    else:
        logger.debug(message, *args)


def _format_legacy_ids(legacy_ids: list[str]) -> str:
    if not legacy_ids:
        return "none"
    unique_ids = list(dict.fromkeys(legacy_ids))
    visible = unique_ids[:10]
    suffix = "" if len(unique_ids) <= 10 else f"...(+{len(unique_ids) - 10})"
    return ",".join(visible) + suffix
