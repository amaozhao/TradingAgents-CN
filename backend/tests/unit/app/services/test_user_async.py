from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.db.ids import DocumentId
from app.services import user as user_module
from app.services.user import UserService
from app.schemas.user import UserCreate


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def skip(self, _count: int):
        return self

    def limit(self, _count: int):
        return self

    async def to_list(self, _length: int | None = None) -> list[dict[str, Any]]:
        return self.documents


class FakeUsersCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.find_one_calls: list[dict[str, Any]] = []
        self.inserted: list[dict[str, Any]] = []
        self.updated: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def find_one(self, query: dict[str, Any], **_kwargs: Any):
        self.find_one_calls.append(query)
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None

    async def insert_one(self, document: dict[str, Any]):
        inserted = dict(document)
        inserted["_id"] = DocumentId()
        self.documents.append(inserted)
        self.inserted.append(inserted)
        return SimpleNamespace(inserted_id=inserted["_id"])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        self.updated.append((query, update))
        return SimpleNamespace(modified_count=1)

    def find(self):
        return FakeCursor([dict(document) for document in self.documents])


def test_user_service_constructor_does_not_open_sync_db(monkeypatch):
    def fail_sync_db():
        raise AssertionError("UserService constructor must not open sync DB")

    monkeypatch.setattr(user_module, "get_postgres_db_sync", fail_sync_db, raising=False)

    service = UserService()

    assert service.client is None


@pytest.mark.asyncio
async def test_create_user_uses_async_collection(monkeypatch):
    users = FakeUsersCollection()

    fake_db = SimpleNamespace(users=users)

    def fail_sync_db():
        raise AssertionError("create_user must not call sync DB")

    async def fake_dual_write(_self: UserService, _document: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(user_module, "get_postgres_db", lambda: fake_db)
    monkeypatch.setattr(user_module, "get_postgres_db_sync", fail_sync_db, raising=False)
    monkeypatch.setattr(UserService, "_dual_write_user", fake_dual_write)

    created = await UserService().create_user(
        UserCreate(username="alice", email="alice@example.test", password="secret")
    )

    assert created is not None
    assert created.username == "alice"
    assert users.find_one_calls == [
        {"username": "alice"},
        {"email": "alice@example.test"},
    ]
    assert users.inserted[0]["username"] == "alice"
