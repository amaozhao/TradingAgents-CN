from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.services import favorites_service, tags_service


@pytest.mark.asyncio
async def test_add_favorite_dual_writes_user_favorite(monkeypatch):
    service = favorites_service.FavoritesService()
    service.db = SimpleNamespace(user_favorites=FakeCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(favorites_service, "dual_write_hot_document", fake_dual_write)

    assert await service.add_favorite("user-1", "000001", "平安银行") is True

    assert dual_write_calls[0][0] == "user_favorites"
    assert dual_write_calls[0][1]["user_id"] == "user-1"
    assert dual_write_calls[0][1]["stock_code"] == "000001"
    assert dual_write_calls[0][1]["stock_name"] == "平安银行"


@pytest.mark.asyncio
async def test_remove_favorite_dual_writes_tombstone(monkeypatch):
    service = favorites_service.FavoritesService()
    service.db = SimpleNamespace(user_favorites=FakeCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(favorites_service, "dual_write_hot_document", fake_dual_write)

    assert await service.remove_favorite("user-1", "000001") is True

    assert dual_write_calls[0][0] == "user_favorites"
    assert dual_write_calls[0][1]["user_id"] == "user-1"
    assert dual_write_calls[0][1]["stock_code"] == "000001"
    assert dual_write_calls[0][1]["deleted"] is True


@pytest.mark.asyncio
async def test_create_tag_dual_writes_user_tag(monkeypatch):
    service = tags_service.TagsService()
    tag_id = ObjectId()
    service.db = SimpleNamespace(user_tags=FakeCollection(inserted_id=tag_id))
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(tags_service, "dual_write_hot_document", fake_dual_write)

    result = await service.create_tag("user-1", "关注", "#409EFF", 1)

    assert result["id"] == str(tag_id)
    assert dual_write_calls[0][0] == "user_tags"
    assert dual_write_calls[0][1]["_id"] == tag_id
    assert dual_write_calls[0][1]["user_id"] == "user-1"
    assert dual_write_calls[0][1]["name"] == "关注"


@pytest.mark.asyncio
async def test_delete_tag_dual_writes_tombstone(monkeypatch):
    service = tags_service.TagsService()
    tag_id = ObjectId()
    service.db = SimpleNamespace(
        user_tags=FakeCollection(
            existing={
                "_id": tag_id,
                "user_id": "user-1",
                "name": "关注",
                "color": "#409EFF",
            }
        )
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(tags_service, "dual_write_hot_document", fake_dual_write)

    assert await service.delete_tag("user-1", str(tag_id)) is True

    assert dual_write_calls[0][0] == "user_tags"
    assert dual_write_calls[0][1]["_id"] == tag_id
    assert dual_write_calls[0][1]["name"] == "关注"
    assert dual_write_calls[0][1]["deleted"] is True


class FakeCollection:
    def __init__(self, inserted_id=None, existing=None):
        self.inserted_id = inserted_id or ObjectId()
        self.existing = existing

    async def create_index(self, *_args, **_kwargs):
        return None

    async def find_one(self, *_args, **_kwargs):
        return self.existing

    async def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id=self.inserted_id)

    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

    async def delete_one(self, *_args, **_kwargs):
        return SimpleNamespace(deleted_count=1)
