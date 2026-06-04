from types import SimpleNamespace

import pytest

from app.scripts import providers as init_providers


@pytest.mark.asyncio
async def test_init_providers_dual_writes_deleted_existing_and_inserted_providers(
    monkeypatch,
):
    fake_collection = FakeProvidersCollection(
        existing=[{"_id": "old-id", "name": "old-provider", "is_active": True}]
    )
    fake_db = SimpleNamespace(llm_providers=fake_collection)
    batch_calls = []
    document_calls = []

    async def fake_init_db():
        return None

    async def fake_dual_write_documents(collection, documents):
        batch_calls.append((collection, [doc.copy() for doc in documents]))
        return SimpleNamespace(status="written", reason="")

    async def fake_dual_write_document(collection, document):
        document_calls.append((collection, document.copy()))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(init_providers, "init_db", fake_init_db)
    monkeypatch.setattr(init_providers, "get_postgres_db", lambda: fake_db)
    monkeypatch.setattr(
        init_providers, "dual_write_hot_documents", fake_dual_write_documents
    )
    monkeypatch.setattr(
        init_providers, "dual_write_hot_document", fake_dual_write_document
    )

    await init_providers.init_providers()

    assert fake_collection.delete_many_queries == [{}]
    assert batch_calls[0][0] == "llm_providers"
    assert batch_calls[0][1][0]["name"] == "old-provider"
    assert batch_calls[0][1][0]["deleted"] is True
    assert batch_calls[0][1][0]["is_active"] is False
    assert len(document_calls) == len(fake_collection.inserted)
    assert document_calls[0][0] == "llm_providers"
    assert document_calls[0][1]["name"] == fake_collection.inserted[0]["name"]


class FakeProvidersCollection:
    def __init__(self, existing):
        self.existing = [doc.copy() for doc in existing]
        self.inserted = []
        self.delete_many_queries = []

    def find(self, _query):
        return FakeCursor(self.existing)

    async def delete_many(self, query):
        self.delete_many_queries.append(query)
        return SimpleNamespace(deleted_count=len(self.existing))

    async def insert_one(self, document):
        self.inserted.append(document.copy())
        return SimpleNamespace(inserted_id=f"inserted-{len(self.inserted)}")


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return [doc.copy() for doc in self.documents]
