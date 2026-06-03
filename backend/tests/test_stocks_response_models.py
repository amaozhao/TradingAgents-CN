from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.routers import stocks


def test_stocks_router_does_not_use_dict_response_model():
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "stocks.py"

    assert "response_model=dict" not in router_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_stocks_router_quote_helper_uses_stock_service_when_postgres_enabled(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    class FakeStockDataService:
        async def get_market_quotes(self, code):
            assert code == "000001"
            return SimpleNamespace(model_dump=lambda exclude_none=True: {"code": code, "close": 10.2})

        async def get_stock_basic_info(self, code, source=None):
            assert code == "000001"
            assert source is None
            return SimpleNamespace(model_dump=lambda exclude_none=True: {"code": code, "name": "平安银行"})

    monkeypatch.setattr(stocks, "StockDataService", FakeStockDataService)

    quote, basic = await stocks._get_cn_quote_and_basic_from_service("000001")

    assert quote == {"code": "000001", "close": 10.2}
    assert basic == {"code": "000001", "name": "平安银行"}


@pytest.mark.asyncio
async def test_stocks_router_helpers_skip_services_when_postgres_disabled(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", False)

    class FailingStockDataService:
        def __init__(self):
            raise AssertionError("service should not be constructed")

    monkeypatch.setattr(stocks, "StockDataService", FailingStockDataService)

    assert await stocks._get_cn_quote_and_basic_from_service("000001") == (None, None)
    assert await stocks._get_cn_basic_from_service("000001", None) is None
    assert await stocks._get_cn_financial_from_service("000001", None) is None


@pytest.mark.asyncio
async def test_stocks_router_financial_helper_uses_financial_service(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    class FakeFinancialDataService:
        async def get_financial_data(self, code, data_source=None, limit=None):
            assert code == "000001"
            assert data_source == "tushare"
            assert limit == 1
            return [{"code": code, "data_source": data_source, "report_period": "2025Q4"}]

    monkeypatch.setattr(stocks, "FinancialDataService", FakeFinancialDataService)

    result = await stocks._get_cn_financial_from_service("000001", "tushare")

    assert result == {"code": "000001", "data_source": "tushare", "report_period": "2025Q4"}
