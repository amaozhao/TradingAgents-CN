import pytest

from app.core.unified import UnifiedConfigManager
from app.schemas.config import DataSourceConfig, DataSourceType


@pytest.mark.asyncio
async def test_unified_system_config_uses_async_data_source_configs(monkeypatch):
    manager = UnifiedConfigManager()

    monkeypatch.setattr(manager, "get_llm_configs", lambda: [])
    monkeypatch.setattr(manager, "get_default_model", lambda: "qwen-turbo")
    monkeypatch.setattr(manager, "get_database_configs", lambda: [])
    monkeypatch.setattr(manager, "get_system_settings", lambda: {})

    def fail_sync_data_sources():
        raise AssertionError("sync data source config loader must not be used")

    async def async_data_sources():
        return [
            DataSourceConfig(
                name="AKShare",
                type=DataSourceType.AKSHARE,
                enabled=True,
                priority=1,
            )
        ]

    monkeypatch.setattr(manager, "get_data_source_configs", fail_sync_data_sources)
    monkeypatch.setattr(manager, "get_data_source_configs_async", async_data_sources)

    config = await manager.get_unified_system_config()

    assert len(config.data_source_configs) == 1
    assert config.data_source_configs[0].type == DataSourceType.AKSHARE
