import pytest
from types import SimpleNamespace

from app.core.config import settings
from app.core import unifiedconfig
from app.services.favorite import FavoritesService


@pytest.mark.asyncio
async def test_get_user_favorites_uses_postgres_entries_and_existing_enrichment(monkeypatch):
    service = FavoritesService()
    db = FakeMongoDB(
        {
            "stock_basic_info": FakeCollection(
                [{"code": "000001", "market": "主板", "sse": "深圳证券交易所"}]
            ),
            "market_quotes": FakeCollection(
                [{"code": "000001", "close": 10.2, "pct_chg": 1.2}]
            ),
        }
    )
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_get_db():
        return db

    monkeypatch.setattr(service, "_get_db", fake_get_db)
    monkeypatch.setattr(unified_config, "UnifiedConfigManager", FakeConfigManager)

    async def fake_pg(user_id):
        assert user_id == "user-1"
        return [
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "market": "A股",
                "tags": ["关注"],
                "notes": "核心持仓",
                "added_at": "2026-06-03T10:00:00",
            }
        ]

    monkeypatch.setattr(service, "_get_user_favorites_from_postgres", fake_pg)

    result = await service.get_user_favorites("user-1")

    assert result[0]["stock_code"] == "000001"
    assert result[0]["stock_name"] == "平安银行"
    assert result[0]["tags"] == ["关注"]
    assert result[0]["current_price"] == 10.2
    assert result[0]["change_percent"] == 1.2
    assert result[0]["board"] == "主板"
    assert result[0]["exchange"] == "深圳证券交易所"


class FakeMongoDB:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, collection):
        return self.collections[collection]


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.documents)


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length=None):
        return self.documents[:length] if length else self.documents


class FakeConfigManager:
    async def get_data_source_configs_async(self):
        return [SimpleNamespace(type="tushare", enabled=True)]
