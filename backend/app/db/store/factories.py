from __future__ import annotations

from .database import (
    PostgresDocumentClient,
    PostgresDocumentDatabase,
    SyncPostgresDocumentClient,
    SyncPostgresDocumentDatabase,
)


def create_database() -> PostgresDocumentDatabase:
    return PostgresDocumentDatabase()


def create_sync_database() -> SyncPostgresDocumentDatabase:
    return SyncPostgresDocumentDatabase()


def create_client() -> PostgresDocumentClient:
    return PostgresDocumentClient()


def create_sync_client() -> SyncPostgresDocumentClient:
    return SyncPostgresDocumentClient()
