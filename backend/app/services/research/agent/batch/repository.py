from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, cast

from app.core.database import get_postgres_db
from app.db.document import normalize_payload
from app.db.dual import dual_write_hot_document, dual_write_hot_documents
from app.utils.timezone import now_tz

from .state import (
    BatchChildState,
    BatchWorkflowState,
    aggregate_batch_status,
    normalize_batch_status_for_document,
)

HotDocumentWriter = Callable[[str, dict[str, Any]], Awaitable[Any]]
HotDocumentsWriter = Callable[[str, list[dict[str, Any]]], Awaitable[Any]]


class _InsertOneCollection(Protocol):
    async def insert_one(self, document: Mapping[str, Any]) -> Any: ...


class _InsertManyCollection(Protocol):
    async def insert_many(self, documents: list[dict[str, Any]]) -> Any: ...


class _FindCollection(Protocol):
    async def find_one(self, query: Mapping[str, Any]) -> dict[str, Any] | None: ...

    def find(self, query: Mapping[str, Any]) -> Any: ...


class _UpdateCollection(Protocol):
    async def update_one(
        self,
        query: Mapping[str, Any],
        update: Mapping[str, Mapping[str, Any]],
    ) -> Any: ...


class _BatchDatabase(Protocol):
    analysis_batches: _InsertOneCollection | _FindCollection | _UpdateCollection
    analysis_tasks: _InsertManyCollection | _FindCollection | _UpdateCollection


class BatchRepository:
    def __init__(
        self,
        *,
        db: _BatchDatabase | None = None,
        hot_document_writer: HotDocumentWriter | None = None,
        hot_documents_writer: HotDocumentsWriter | None = None,
    ) -> None:
        self._db = db
        self._hot_document_writer = hot_document_writer or dual_write_hot_document
        self._hot_documents_writer = hot_documents_writer or dual_write_hot_documents

    @property
    def db(self) -> _BatchDatabase:
        if self._db is None:
            self._db = cast(_BatchDatabase, get_postgres_db())
        return self._db

    async def save_submitted_batch(self, state: BatchWorkflowState) -> None:
        batch_document = _batch_document(state)
        task_documents = [_task_document(state, child) for child in state.children]

        batches = cast(_InsertOneCollection, self.db.analysis_batches)
        await batches.insert_one(batch_document)
        await self._hot_document_writer("analysis_batches", batch_document)

        if not task_documents:
            return
        tasks = cast(_InsertManyCollection, self.db.analysis_tasks)
        await tasks.insert_many(task_documents)
        await self._hot_documents_writer("analysis_tasks", task_documents)

    async def update_child(
        self,
        batch_id: str,
        user_id: str,
        child: BatchChildState,
    ) -> bool:
        update = _child_update_document(child)
        tasks = cast(_UpdateCollection, self.db.analysis_tasks)
        result = await tasks.update_one(
            {"batch_id": batch_id, "user_id": user_id, "task_id": child.task_id},
            {"$set": update},
        )
        if _matched_count(result) == 0:
            return False
        await self._hot_document_writer(
            "analysis_tasks",
            {
                "batch_id": batch_id,
                "user_id": user_id,
                "task_id": child.task_id,
                "symbol": child.symbol,
                "stock_code": child.stock_code,
                "stock_symbol": child.symbol,
                **update,
            },
        )
        return True

    async def update_batch_aggregate(self, state: BatchWorkflowState) -> bool:
        update = _batch_aggregate_document(state)
        batches = cast(_UpdateCollection, self.db.analysis_batches)
        result = await batches.update_one(
            {"batch_id": state.batch_id, "user_id": state.user_id},
            {"$set": update},
        )
        if _matched_count(result) == 0:
            return False
        await self._hot_document_writer(
            "analysis_batches",
            {"batch_id": state.batch_id, "user_id": state.user_id, **update},
        )
        return True

    async def get_batch(self, batch_id: str, user_id: str) -> dict[str, Any] | None:
        batches = cast(_FindCollection, self.db.analysis_batches)
        batch = await batches.find_one({"batch_id": batch_id, "user_id": user_id})
        if batch is None:
            return None
        tasks = cast(_FindCollection, self.db.analysis_tasks)
        batch["tasks"] = await _cursor_to_list(
            tasks.find({"batch_id": batch_id, "user_id": user_id})
        )
        return batch


def _batch_document(state: BatchWorkflowState) -> dict[str, Any]:
    created_at = state.created_at or now_tz()
    aggregate = aggregate_batch_status(state)
    return {
        "batch_id": state.batch_id,
        "user_id": state.user_id,
        "title": state.title,
        "description": state.description,
        "status": normalize_batch_status_for_document(state.status),
        "total_tasks": aggregate.total_tasks,
        "completed_tasks": aggregate.completed_tasks,
        "failed_tasks": aggregate.failed_tasks,
        "cancelled_tasks": aggregate.cancelled_tasks,
        "progress": 0 if state.status == "pending" else aggregate.progress,
        "parameters": normalize_payload(state.parameters),
        "results_summary": _results_summary(state),
        "mapping": _mapping(state),
        "created_at": created_at,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
    }


def _task_document(
    state: BatchWorkflowState,
    child: BatchChildState,
) -> dict[str, Any]:
    return {
        "task_id": child.task_id,
        "batch_id": state.batch_id,
        "user_id": state.user_id,
        "symbol": child.symbol,
        "stock_code": child.stock_code,
        "stock_symbol": child.symbol,
        "status": child.status,
        "progress": child.progress,
        "parameters": normalize_payload(state.parameters),
        "created_at": state.created_at or now_tz(),
        "analysis_id": child.analysis_id,
        "report_url": child.report_url,
        "last_error": child.error,
    }


def _child_update_document(child: BatchChildState) -> dict[str, Any]:
    update: dict[str, Any] = {
        "status": child.status,
        "progress": child.progress,
        "updated_at": now_tz(),
    }
    if child.analysis_id:
        update["analysis_id"] = child.analysis_id
    if child.report_url:
        update["report_url"] = child.report_url
    if child.error:
        update["last_error"] = child.error
    if child.status in {"completed", "failed", "cancelled"}:
        update["completed_at"] = now_tz()
    return update


def _batch_aggregate_document(state: BatchWorkflowState) -> dict[str, Any]:
    aggregate = aggregate_batch_status(state)
    status = normalize_batch_status_for_document(aggregate.status)
    update: dict[str, Any] = {
        "status": status,
        "total_tasks": aggregate.total_tasks,
        "completed_tasks": aggregate.completed_tasks,
        "failed_tasks": aggregate.failed_tasks,
        "cancelled_tasks": aggregate.cancelled_tasks,
        "progress": aggregate.progress,
        "results_summary": _results_summary(state),
        "mapping": _mapping(state),
        "updated_at": now_tz(),
    }
    if aggregate.status in {"completed", "partial", "failed", "cancelled"}:
        update["completed_at"] = state.completed_at or now_tz()
    return update


def _results_summary(state: BatchWorkflowState) -> dict[str, Any]:
    aggregate = aggregate_batch_status(state)
    return {
        "status": normalize_batch_status_for_document(aggregate.status),
        "total_tasks": aggregate.total_tasks,
        "completed_tasks": aggregate.completed_tasks,
        "failed_tasks": aggregate.failed_tasks,
        "cancelled_tasks": aggregate.cancelled_tasks,
        "processing_tasks": aggregate.processing_tasks,
        "progress": aggregate.progress,
        "mapping": _mapping(state),
        "children": [_child_summary(child) for child in state.children],
    }


def _mapping(state: BatchWorkflowState) -> dict[str, str]:
    return {child.symbol: child.task_id for child in state.children}


def _child_summary(child: BatchChildState) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "symbol": child.symbol,
        "stock_code": child.stock_code,
        "task_id": child.task_id,
        "status": child.status,
        "progress": child.progress,
    }
    if child.analysis_id:
        summary["analysis_id"] = child.analysis_id
    if child.report_url:
        summary["report_url"] = child.report_url
    if child.error:
        summary["error"] = child.error
    return summary


async def _cursor_to_list(cursor: Any) -> list[dict[str, Any]]:
    if hasattr(cursor, "to_list"):
        documents = await cursor.to_list(length=None)
        return [dict(document) for document in documents]
    return [dict(document) async for document in cursor]


def _matched_count(result: Any) -> int:
    return int(getattr(result, "matched_count", 0) or 0)
