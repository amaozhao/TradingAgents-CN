from __future__ import annotations

from typing import Self, cast

from sqlalchemy import select

from app.core.session import get_session_factory
from app.models.table import PostgresDocument

from .collection import PostgresCollection
from .helpers import _ensure_postgres, _run_blocking
from .imports import CONFIG_COLLECTIONS, SPECIALIZED_MODELS
from .sync import SyncPostgresCollection


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
