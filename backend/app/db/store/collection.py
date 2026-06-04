from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select

from app.core.session import get_session_factory
from app.db.document import normalize_payload
from app.models.table import PostgresDocument

from .cursor import PostgresCursor
from .helpers import (
    _apply_update,
    _build_specialized_select,
    _document_id_from_filter,
    _ensure_document_id,
    _ensure_postgres,
    _get_value,
    _group_documents,
    _matches,
    _merge_filter_identity,
    _model_for_collection,
    _new_document_id,
    _project,
    _row_to_document,
    _write_specialized_table,
    build_document_upsert,
)
from .imports import CONFIG_COLLECTIONS
from .results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)


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
        **ignored_kwargs,
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
        **ignored_kwargs,
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
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
        **ignored_kwargs,
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
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
        **ignored_kwargs,
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

    def aggregate(
        self, pipeline: list[dict[str, Any]], *_, **ignored_kwargs
    ) -> PostgresCursor:
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

    async def create_index(self, *_, **ignored_kwargs) -> str:
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
