import pytest

from trader.flows.providers.us.alpha import common as alpha_common


class ActiveConfigCollection:
    async def find_one(self, *_args, **_kwargs):
        return {
            "data_source_configs": [
                {
                    "type": "alpha_vantage",
                    "name": "alpha_vantage",
                    "api_key": "db-alpha-key",
                }
            ]
        }


class AsyncDb:
    system_configs = ActiveConfigCollection()


@pytest.mark.asyncio
async def test_get_api_key_async_uses_async_database(monkeypatch):
    import app.core.database as database

    def sync_db_called():
        raise AssertionError("async alpha key loader must not use sync DB")

    monkeypatch.setattr(database, "get_postgres_db_sync", sync_db_called)
    monkeypatch.setattr(database, "get_postgres_db", lambda: AsyncDb())

    key = await alpha_common.get_api_key_async()

    assert key == "db-alpha-key"
