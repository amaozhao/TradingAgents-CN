from types import SimpleNamespace

import pytest

from app.services import financialdataservice
from app.services.financialdataservice import FinancialDataService


@pytest.mark.asyncio
async def test_save_financial_data_dual_writes_standardized_records(monkeypatch):
    service = FinancialDataService()
    service.db = FakeDB()

    dual_write_calls = []

    async def fake_dual_write(collection, documents):
        dual_write_calls.append((collection, documents))

    monkeypatch.setattr(financial_data_service, "dual_write_hot_documents", fake_dual_write)

    saved = await service.save_financial_data(
        symbol="000001",
        financial_data={"report_period": "2025Q4", "roe": 12.3, "gross_margin": 44.1},
        data_source="tushare",
        report_period="2025Q4",
    )

    assert saved == 1
    assert dual_write_calls[0][0] == "stock_financial_data"
    assert dual_write_calls[0][1][0]["code"] == "000001"
    assert dual_write_calls[0][1][0]["data_source"] == "tushare"
    assert dual_write_calls[0][1][0]["report_period"] == "2025Q4"
    assert dual_write_calls[0][1][0]["roe"] == 12.3


class FakeDB:
    def __getitem__(self, _collection):
        return FakeBulkCollection()


class FakeBulkCollection:
    async def bulk_write(self, operations):
        return SimpleNamespace(upserted_count=len(operations), modified_count=0)
