from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.routers import system as system_module


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    async def to_list(self, _length: int | None = None) -> list[dict[str, Any]]:
        return self.documents


class FakeProvidersCollection:
    def find(self) -> FakeCursor:
        return FakeCursor(
            [
                {
                    "name": "qwen",
                    "display_name": "通义千问",
                    "is_active": True,
                    "api_key": "db-valid-key",
                }
            ]
        )


@pytest.mark.asyncio
async def test_validate_config_reads_llm_providers_with_async_cursor(monkeypatch):
    bridge_calls: list[str] = []

    class FakeDb:
        llm_providers = FakeProvidersCollection()

    class FakeValidator:
        def validate(self):
            return SimpleNamespace(
                success=True,
                missing_required=[],
                missing_recommended=[],
                invalid_configs=[],
                warnings=[],
            )

    class FakeConfigService:
        async def get_system_config(self):
            return SimpleNamespace(data_source_configs=[])

    async def fake_async_bridge():
        bridge_calls.append("async")
        return True

    def fake_import(name: str):
        if name == "app.core.startup":
            return SimpleNamespace(StartupValidator=FakeValidator)
        if name == "app.core.bridge":
            return SimpleNamespace(
                bridge_config_to_env=lambda: (_ for _ in ()).throw(
                    AssertionError("validate_config must use async bridge")
                ),
                bridge_config_to_env_async=fake_async_bridge,
            )
        if name == "app.services.config":
            return SimpleNamespace(config_service=FakeConfigService())
        if name == "app.utils.keys":
            return SimpleNamespace(
                is_valid_api_key=lambda value: bool(value),
                get_env_api_key_for_provider=lambda _provider: None,
                get_env_api_key_for_datasource=lambda _source: None,
            )
        if name == "app.core.database":
            return SimpleNamespace(
                get_postgres_db=lambda: FakeDb(),
                get_postgres_db_sync=lambda: (_ for _ in ()).throw(
                    AssertionError("validate_config must not call sync DB")
                ),
            )
        return system_module.importlib.import_module(name)

    real_import = system_module.importlib.import_module

    def guarded_import(name: str):
        if name == "app.schemas.config":
            return real_import(name)
        return fake_import(name)

    monkeypatch.setattr(system_module.importlib, "import_module", guarded_import)

    result = await system_module.validate_config()

    providers = result["data"]["postgres_validation"]["llm_providers"]
    assert bridge_calls == ["async"]
    assert providers[0]["name"] == "qwen"
    assert providers[0]["source"] == "database"
