from __future__ import annotations

from types import SimpleNamespace

from app.services.config import ConfigService


class FakeSystemConfigsCollection:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def find_one(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.result


class FakeDatabase:
    def __init__(self, system_config):
        self.system_configs = FakeSystemConfigsCollection(system_config)


def active_system_config_document():
    return {
        "config_name": "测试配置",
        "config_type": "system",
        "llm_configs": [
            {
                "provider": "qwen",
                "model_name": "qwen-plus",
                "api_key": "test-key",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "enabled": True,
            }
        ],
        "default_llm": "qwen-plus",
        "data_source_configs": [],
        "default_data_source": "AKShare",
        "database_configs": [],
        "system_settings": {"max_concurrent_tasks": 3},
        "is_active": True,
        "version": 7,
    }


async def test_system_config_reads_active_document_with_async_collection():
    database = FakeDatabase(active_system_config_document())
    service = ConfigService(db_manager=SimpleNamespace(postgres_db=database))

    config = await service.get_system_config()

    assert config is not None
    assert config.config_name == "测试配置"
    assert config.default_llm == "qwen-plus"
    assert database.system_configs.calls == [
        ({"is_active": True}, {"sort": [("version", -1)]})
    ]


async def test_system_config_creates_default_when_active_document_missing(monkeypatch):
    database = FakeDatabase(None)
    service = ConfigService(db_manager=SimpleNamespace(postgres_db=database))
    created = object()

    async def fake_create_default_config():
        return created

    monkeypatch.setattr(service, "_create_default_config", fake_create_default_config)

    config = await service.get_system_config()

    assert config is created
    assert database.system_configs.calls == [
        ({"is_active": True}, {"sort": [("version", -1)]})
    ]
