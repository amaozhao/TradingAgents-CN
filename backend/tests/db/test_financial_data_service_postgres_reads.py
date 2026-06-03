from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.financial_data_service import FinancialDataService


@pytest.mark.asyncio
async def test_get_financial_data_uses_postgres_when_enabled(monkeypatch):
    service = FinancialDataService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(**kwargs):
        assert kwargs["symbol"] == "000001"
        assert kwargs["data_source"] == "tushare"
        return [{"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}]

    monkeypatch.setattr(service, "_get_financial_data_from_postgres", fake_pg)

    results = await service.get_financial_data("000001", data_source="tushare")

    assert results == [{"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}]


@pytest.mark.asyncio
async def test_get_financial_data_falls_back_to_mongo_when_postgres_misses(monkeypatch):
    service = FinancialDataService()
    service.db = FakeDB()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(**_kwargs):
        return []

    monkeypatch.setattr(service, "_get_financial_data_from_postgres", fake_pg)

    results = await service.get_financial_data("000001", data_source="tushare", limit=1)

    assert results == [{"symbol": "000001", "data_source": "tushare", "report_period": "2025Q4"}]


class FakeDB:
    def __getitem__(self, _collection):
        return FakeCollection()


class FakeCollection:
    def find(self, *_args, **_kwargs):
        return FakeCursor()


class FakeCursor:
    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, *_args, **_kwargs):
        return [{"symbol": "000001", "data_source": "tushare", "report_period": "2025Q4"}]
