import pytest

from app.core import bridge


class AsyncCursor:
    async def to_list(self, _length):
        return [
            {
                "name": "dashscope",
                "display_name": "DashScope",
                "is_active": True,
                "api_key": "db-dashscope-key",
            }
        ]


class ProviderCollection:
    def find(self):
        return AsyncCursor()


class ConfigCollection:
    async def find_one(self, *_args, **_kwargs):
        return {
            "config_name": "active",
            "config_type": "system",
            "is_active": True,
            "data_source_configs": [
                {
                    "name": "Tushare",
                    "type": "tushare",
                    "api_key": "db-tushare-token",
                    "enabled": True,
                    "priority": 2,
                }
            ],
            "system_settings": {
                "app_timezone": "Asia/Shanghai",
                "enable_cost_tracking": True,
            },
        }


class AsyncDb:
    llm_providers = ProviderCollection()
    system_configs = ConfigCollection()


@pytest.mark.asyncio
async def test_async_bridge_uses_async_database_without_sync_facade(monkeypatch):
    from app.core import database
    from app.core import unified

    def fail_sync_db():
        raise AssertionError("sync database facade must not be used")

    reinit_calls: list[str] = []

    def fake_reinitialize_storage():
        reinit_calls.append("reinit")

    async def skip_pricing_sync():
        return None

    async def fake_to_thread(func, *args, **kwargs):
        reinit_calls.append("thread")
        return func(*args, **kwargs)

    monkeypatch.setattr(database, "get_postgres_db_sync", fail_sync_db)
    monkeypatch.setattr(database, "get_postgres_db", lambda: AsyncDb())
    monkeypatch.setattr(bridge, "_reinitialize_trading_agents_postgres_storage", fake_reinitialize_storage)
    monkeypatch.setattr(bridge.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(bridge, "_sync_pricing_config_from_db", skip_pricing_sync)
    monkeypatch.setattr(unified.unified_config, "save_system_settings", lambda _settings: True)
    bridge.clear_bridged_config()

    success = await bridge.bridge_config_to_env_async()

    assert success is True
    assert bridge.get_bridged_api_key("dashscope") == "db-dashscope-key"
    assert bridge._BRIDGED_VALUES["TUSHARE_TOKEN"] == "db-tushare-token"
    assert reinit_calls == ["thread", "reinit"]
