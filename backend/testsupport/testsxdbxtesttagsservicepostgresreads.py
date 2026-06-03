import pytest

from app.core.coreconfig import settings
from app.services.tagsservice import TagsService


@pytest.mark.asyncio
async def test_list_tags_uses_postgres_when_enabled(monkeypatch):
    service = TagsService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(user_id):
        assert user_id == "user-1"
        return [
            {
                "id": "tag-1",
                "name": "关注",
                "color": "#409EFF",
                "sort_order": 1,
                "created_at": "2026-06-03T10:00:00",
                "updated_at": "2026-06-03T10:00:00",
            }
        ]

    monkeypatch.setattr(service, "_list_tags_from_postgres", fake_pg)

    result = await service.list_tags("user-1")

    assert result == [
        {
            "id": "tag-1",
            "name": "关注",
            "color": "#409EFF",
            "sort_order": 1,
            "created_at": "2026-06-03T10:00:00",
            "updated_at": "2026-06-03T10:00:00",
        }
    ]
