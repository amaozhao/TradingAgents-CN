from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.models.user import UserCreate
from app.services import user_service


@pytest.mark.asyncio
async def test_create_user_dual_writes_user_account(monkeypatch):
    service = user_service.UserService.__new__(user_service.UserService)
    service.users_collection = FakeUsersCollection()
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(user_service, "dual_write_hot_document", fake_dual_write)

    created = await service.create_user(
        UserCreate(username="demo", email="demo@example.com", password="secret")
    )

    assert created is not None
    assert dual_write_calls[0][0] == "users"
    assert dual_write_calls[0][1]["username"] == "demo"
    assert dual_write_calls[0][1]["email"] == "demo@example.com"
    assert dual_write_calls[0][1]["is_active"] is True


@pytest.mark.asyncio
async def test_authenticate_user_dual_writes_last_login(monkeypatch):
    service = user_service.UserService.__new__(user_service.UserService)
    user_id = ObjectId()
    stored = {
        "_id": user_id,
        "username": "demo",
        "email": "demo@example.com",
        "hashed_password": user_service.UserService.hash_password("secret"),
        "is_active": True,
        "is_verified": False,
        "is_admin": False,
    }
    service.users_collection = FakeUsersCollection(existing=stored)
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(user_service, "dual_write_hot_document", fake_dual_write)

    authenticated = await service.authenticate_user("demo", "secret")

    assert authenticated is not None
    assert dual_write_calls[0][0] == "users"
    assert dual_write_calls[0][1]["username"] == "demo"
    assert "last_login" in dual_write_calls[0][1]


class FakeUsersCollection:
    def __init__(self, existing=None):
        self.existing = existing
        self.inserted_id = ObjectId()
        self.inserted = None
        self.updated = []

    def find_one(self, query, *_args, **_kwargs):
        if self.existing and (
            query.get("username") == self.existing.get("username")
            or query.get("email") == self.existing.get("email")
            or query.get("_id") == self.existing.get("_id")
        ):
            return self.existing
        return None

    def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id=self.inserted_id)

    def update_one(self, *args, **kwargs):
        self.updated.append((args, kwargs))
        return SimpleNamespace(matched_count=1, modified_count=1)
