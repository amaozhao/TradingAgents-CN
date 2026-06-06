import importlib

import pytest


def _type_values(configs):
    return [str(config.type.value if hasattr(config.type, "value") else config.type) for config in configs]


def test_sync_fallback_includes_free_a_share_sources(monkeypatch):
    unified_module = importlib.import_module("app.core.unified")
    manager = unified_module.UnifiedConfigManager()

    real_import_module = unified_module.importlib.import_module

    def fake_import_module(name):
        if name == "app.core.database":
            raise RuntimeError("force fallback")
        return real_import_module(name)

    monkeypatch.setattr(unified_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(manager, "get_system_settings", lambda: {})

    configs = manager.get_data_source_configs()

    source_types = _type_values(configs)
    assert "akshare" in source_types
    assert "baostock" in source_types
    assert all(config.enabled for config in configs if str(config.type.value) in {"akshare", "baostock"})


@pytest.mark.asyncio
async def test_async_fallback_includes_free_a_share_sources(monkeypatch):
    unified_module = importlib.import_module("app.core.unified")
    manager = unified_module.UnifiedConfigManager()

    real_import_module = unified_module.importlib.import_module

    def fake_import_module(name):
        if name == "app.core.database":
            raise RuntimeError("force fallback")
        return real_import_module(name)

    monkeypatch.setattr(unified_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(manager, "get_system_settings", lambda: {})

    configs = await manager.get_data_source_configs_async()

    source_types = _type_values(configs)
    assert "akshare" in source_types
    assert "baostock" in source_types
    assert all(config.enabled for config in configs if str(config.type.value) in {"akshare", "baostock"})
