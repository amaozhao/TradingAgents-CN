import pytest
import pandas as pd

from app.services.screening import service as screening_service
from app.services.screening.service import ScreeningParams, ScreeningService


class AsyncCursor:
    async def to_list(self, _length):
        return [{"code": "000001"}, {"code": "600519"}]


class AsyncCollection:
    def find(self, *_args, **_kwargs):
        return AsyncCursor()


class AsyncDb:
    stock_basic_info = AsyncCollection()


@pytest.mark.asyncio
async def test_run_async_loads_universe_with_async_database(monkeypatch):
    monkeypatch.setattr(screening_service, "get_postgres_db", lambda: AsyncDb())

    service = ScreeningService()
    monkeypatch.setattr(
        service,
        "_get_universe",
        lambda: (_ for _ in ()).throw(
            AssertionError("sync universe loader must not be used")
        ),
    )

    result = await service.run_async({}, ScreeningParams(limit=10))

    assert result["total"] == 2
    assert [item["code"] for item in result["items"]] == ["000001", "600519"]


@pytest.mark.asyncio
async def test_run_async_uses_async_trader_data_source_manager(monkeypatch):
    import trader.flows.sources as sources

    monkeypatch.setattr(screening_service, "get_postgres_db", lambda: AsyncDb())

    def fail_sync_manager():
        raise AssertionError("sync data source manager must not be used")

    class FakeManager:
        def get_stock_dataframe(self, *_args):
            return pd.DataFrame(
                [
                    {
                        "Open": 9.5,
                        "High": 10.5,
                        "Low": 9.0,
                        "Close": 10.0,
                        "Volume": 1000,
                        "Amount": 10000,
                    }
                ]
            )

    async def get_async_manager():
        return FakeManager()

    monkeypatch.setattr(sources, "get_data_source_manager", fail_sync_manager)
    monkeypatch.setattr(sources, "get_data_source_manager_async", get_async_manager)

    service = ScreeningService()
    result = await service.run_async(
        {"field": "close", "op": ">", "value": 1},
        ScreeningParams(limit=10),
    )

    assert result["total"] == 2
    assert [item["code"] for item in result["items"]] == ["000001", "600519"]
