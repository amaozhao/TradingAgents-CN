from __future__ import annotations


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    async def find_one(self, query, **kwargs):
        if query == {"is_active": True}:
            return self.documents[0] if self.documents else None
        name = query.get("name")
        for document in self.documents:
            if document.get("name") == name:
                return document
        return None


class FakeDatabase:
    def __init__(self, system_config, providers):
        self.system_configs = FakeCollection([system_config] if system_config else [])
        self.llm_providers = FakeCollection(providers)


async def test_async_provider_resolver_uses_model_config_before_provider(monkeypatch):
    from app.core import database
    from app.services.analysis.simple import provider

    def fail_sync_lookup():
        raise AssertionError("async resolver must not call get_postgres_db_sync")

    monkeypatch.setattr(database, "get_postgres_db_sync", fail_sync_lookup)
    monkeypatch.setattr(
        database,
        "get_postgres_db",
        lambda: FakeDatabase(
            {
                "is_active": True,
                "llm_configs": [
                    {
                        "provider": "qwen",
                        "model_name": "qwen-plus",
                        "api_key": "model-key",
                        "api_base": "https://model.example/v1",
                        "enabled": True,
                    }
                ],
            },
            [
                {
                    "name": "qwen",
                    "api_key": "provider-key",
                    "default_base_url": "https://provider.example/v1",
                }
            ],
        ),
    )

    result = await provider.get_provider_and_url_by_model("qwen-plus")

    assert result == {
        "provider": "qwen",
        "backend_url": "https://model.example/v1",
        "api_key": "model-key",
    }


async def test_async_provider_resolver_falls_back_to_provider_config(monkeypatch):
    from app.core import database
    from app.services.analysis.simple import provider

    monkeypatch.setattr(
        database,
        "get_postgres_db",
        lambda: FakeDatabase(
            {
                "is_active": True,
                "llm_configs": [],
            },
            [
                {
                    "name": "qwen",
                    "api_key": "provider-key",
                    "default_base_url": "https://provider.example/v1",
                }
            ],
        ),
    )

    result = await provider.get_provider_and_url_by_model("qwen-plus")

    assert result == {
        "provider": "qwen",
        "backend_url": "https://provider.example/v1",
        "api_key": "provider-key",
    }


async def test_async_analysis_config_uses_async_provider_resolver(monkeypatch):
    from app.services.analysis.simple import provider

    async def async_provider_info(model_name: str) -> dict[str, str]:
        return {
            "provider": "qwen",
            "backend_url": f"https://{model_name}.example/v1",
            "api_key": f"{model_name}-key",
        }

    def sync_provider_info(_model_name: str) -> dict[str, str]:
        raise AssertionError(
            "async analysis config must not call sync provider resolver"
        )

    monkeypatch.setattr(
        provider,
        "get_provider_and_url_by_model",
        async_provider_info,
    )
    monkeypatch.setattr(
        provider,
        "get_provider_and_url_by_model_sync",
        sync_provider_info,
    )

    config = await provider.create_analysis_config_async(
        research_depth="标准",
        selected_analysts=["market"],
        quick_model="qwen-plus",
        deep_model="qwen-max",
        llm_provider="qwen",
    )

    assert config["backend_url"] == "https://qwen-plus.example/v1"
    assert config["quick_api_key"] == "qwen-plus-key"
    assert config["deep_api_key"] == "qwen-max-key"
