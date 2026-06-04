from types import SimpleNamespace

import pytest

from app.schemas.config import MarketCategory
from app.services import config as config_service


@pytest.mark.asyncio
async def test_add_market_category_dual_writes_config_document(monkeypatch):
    service = config_service.ConfigService()
    service.db = SimpleNamespace(market_categories=FakeCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(config_service, "dual_write_hot_document", fake_dual_write)

    result = await service.add_market_category(
        MarketCategory(
            id="a_shares",
            name="a_shares",
            display_name="A股",
        )
    )

    assert result is True
    assert dual_write_calls[0][0] == "market_categories"
    assert dual_write_calls[0][1]["id"] == "a_shares"
    assert dual_write_calls[0][1]["enabled"] is True


@pytest.mark.asyncio
async def test_update_llm_provider_dual_writes_partial_provider_document(monkeypatch):
    service = config_service.ConfigService()
    service.db = SimpleNamespace(llm_providers=FakeCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(config_service, "dual_write_hot_document", fake_dual_write)

    result = await service.update_llm_provider(
        "provider-1", {"display_name": "Provider"}
    )

    assert result is True
    assert dual_write_calls[0][0] == "llm_providers"
    assert dual_write_calls[0][1]["_id"] == "provider-1"
    assert dual_write_calls[0][1]["display_name"] == "Provider"
    assert "updated_at" in dual_write_calls[0][1]


class FakeCollection:
    async def find_one(self, *_args, **_kwargs):
        return None

    async def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id="postgres-id")

    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(matched_count=1, modified_count=1)
