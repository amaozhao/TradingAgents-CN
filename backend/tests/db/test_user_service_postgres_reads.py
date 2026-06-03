from datetime import datetime
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.core.config import settings
from app.services import user_service


@pytest.mark.asyncio
async def test_get_user_by_username_uses_valid_postgres_document(monkeypatch):
    service = user_service.UserService.__new__(user_service.UserService)
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    user_id = ObjectId()

    async def fake_pg_user(**kwargs):
        assert kwargs["username"] == "demo"
        return _user_doc(user_id=user_id)

    monkeypatch.setattr(service, "_get_user_document_from_postgres", fake_pg_user)

    user = await service.get_user_by_username("demo")

    assert user is not None
    assert str(user.id) == str(user_id)
    assert user.username == "demo"


@pytest.mark.asyncio
async def test_authenticate_user_uses_postgres_and_updates_mongo_with_object_id(monkeypatch):
    service = user_service.UserService.__new__(user_service.UserService)
    service.users_collection = FakeUsersCollection()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)
    user_id = ObjectId()
    dual_write_calls = []

    async def fake_pg_user(**kwargs):
        assert kwargs["username"] == "demo"
        return _user_doc(user_id=user_id)

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(service, "_get_user_document_from_postgres", fake_pg_user)
    monkeypatch.setattr(user_service, "dual_write_hot_document", fake_dual_write)

    authenticated = await service.authenticate_user("demo", "secret")

    assert authenticated is not None
    assert service.users_collection.updated[0][0][0] == {"_id": user_id}
    assert dual_write_calls[0][0] == "users"
    assert dual_write_calls[0][1]["_id"] == str(user_id)
    assert "last_login" in dual_write_calls[0][1]


def test_invalid_postgres_user_legacy_id_is_rejected_before_user_model():
    service = user_service.UserService.__new__(user_service.UserService)

    document = _user_doc(user_id="user_accounts:demo")

    assert service._validated_postgres_user_document(document) is None


def _user_doc(user_id) -> dict:
    return {
        "_id": str(user_id),
        "username": "demo",
        "email": "demo@example.com",
        "hashed_password": user_service.UserService.hash_password("secret"),
        "is_active": True,
        "is_verified": False,
        "is_admin": False,
        "created_at": datetime(2026, 6, 3, 10, 0, 0),
        "updated_at": datetime(2026, 6, 3, 10, 0, 0),
    }


class FakeUsersCollection:
    def __init__(self):
        self.updated = []

    def update_one(self, *args, **kwargs):
        self.updated.append((args, kwargs))
        return SimpleNamespace(matched_count=1, modified_count=1)
