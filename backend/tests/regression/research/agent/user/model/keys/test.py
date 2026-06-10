from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.routers.user.model import keys as user_model_keys_router
from app.services.research.agent.user.model import keys as user_model_keys_module
from app.services.research.agent.user.model.keys import UserModelKeyService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}
PRIVATE_KEY = "sk-real-private-key-1234567890"


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if document.get(key) != expected:
            return False
    return True


class FakeInsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class FakeDeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class FakeUpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, *_args):
        return self

    def __aiter__(self):
        self._iter = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self):
        self.documents: list[dict[str, Any]] = []
        self.last_find_query: dict[str, Any] | None = None

    async def insert_one(self, document: dict[str, Any]):
        self.documents.append(dict(document))
        return FakeInsertResult(str(document["_id"]))

    def find(self, query: dict[str, Any]):
        self.last_find_query = query
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def find_one(self, query: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                return dict(document)
        return None

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                document.update(update.get("$set", {}))
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    async def delete_one(self, query: dict[str, Any]):
        before = len(self.documents)
        self.documents = [
            document
            for document in self.documents
            if not _matches_query(document, query)
        ]
        return FakeDeleteResult(before - len(self.documents))


class FakeDb:
    def __init__(self):
        self.user_model_keys = FakeCollection()
        self.llm_providers = FakeCollection()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(user_model_keys_module, "get_postgres_db", lambda: db)
    return db


@pytest.mark.asyncio
async def test_service_creates_lists_redacted_keys_without_plaintext_storage(fake_db):
    service = UserModelKeyService()

    created = await service.create_key(
        user_id=USER_A["id"],
        provider="minimax-token-plan",
        model="MiniMax-M2",
        api_key=PRIVATE_KEY,
        display_name="MiniMax private key",
    )
    listed = await service.list_keys(user_id=USER_A["id"])
    resolved = await service.resolve_key_for_agent(
        user_id=USER_A["id"],
        provider="minimax-token-plan",
        model="MiniMax-M2",
    )

    assert created["provider"] == "minimax-token-plan"
    assert created["api_key"] == "****"
    assert listed[0]["api_key"] == "****"
    assert PRIVATE_KEY not in str(created)
    assert PRIVATE_KEY not in str(listed[0])
    assert PRIVATE_KEY not in str(fake_db.user_model_keys.documents[0])
    assert "encrypted_api_key" in fake_db.user_model_keys.documents[0]
    assert resolved == PRIVATE_KEY
    assert fake_db.llm_providers.documents == []


@pytest.mark.asyncio
async def test_service_owner_scopes_list_read_update_and_delete(fake_db):
    service = UserModelKeyService()
    key = await service.create_key(
        user_id=USER_B["id"],
        provider="minimax-token-plan",
        model="MiniMax-M2",
        api_key=PRIVATE_KEY,
    )

    assert await service.list_keys(user_id=USER_A["id"]) == []
    assert await service.get_key(user_id=USER_A["id"], key_id=key["id"]) is None
    assert (
        await service.update_key(
            user_id=USER_A["id"],
            key_id=key["id"],
            display_name="stolen",
            api_key="sk-attacker-private-key",
        )
        is None
    )
    assert await service.delete_key(user_id=USER_A["id"], key_id=key["id"]) is False

    updated = await service.update_key(
        user_id=USER_B["id"],
        key_id=key["id"],
        display_name="updated",
        api_key="sk-updated-private-key",
    )

    assert updated is not None
    assert updated["display_name"] == "updated"
    assert updated["api_key"] == "****"
    assert (
        await service.resolve_key_for_agent(
            user_id=USER_B["id"],
            provider="minimax-token-plan",
            model="MiniMax-M2",
        )
        == "sk-updated-private-key"
    )
    assert await service.delete_key(user_id=USER_B["id"], key_id=key["id"]) is True


@pytest.mark.asyncio
async def test_routes_redact_audit_payloads_and_reject_other_users(
    fake_db, monkeypatch
):
    service = UserModelKeyService()
    monkeypatch.setattr(user_model_keys_router, "user_model_key_service", service)
    audit_events: list[dict[str, Any]] = []

    async def capture_log_operation(**kwargs):
        audit_events.append(kwargs)

    monkeypatch.setattr(user_model_keys_router, "log_operation", capture_log_operation)

    created_response = await user_model_keys_router.create_user_model_key(
        user_model_keys_router.UserModelKeyCreateRequest(
            provider="minimax-token-plan",
            model="MiniMax-M2",
            api_key=PRIVATE_KEY,
            display_name="route key",
        ),
        current_user=USER_A,
    )

    key_id = created_response["data"]["id"]
    assert created_response["data"]["api_key"] == "****"
    assert PRIVATE_KEY not in str(created_response)
    assert PRIVATE_KEY not in str(audit_events)

    with pytest.raises(HTTPException) as exc:
        await user_model_keys_router.get_user_model_key(key_id, current_user=USER_B)

    assert exc.value.status_code == 404
