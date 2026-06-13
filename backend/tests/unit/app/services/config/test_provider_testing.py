from __future__ import annotations

from typing import Any

import pytest

from app.services.config.testing.provider import ProviderApiTestMixin


class FakeProvidersCollection:
    def __init__(self, provider_data: dict[str, Any]) -> None:
        self._provider_data = provider_data

    async def find_one(self, _query: dict[str, Any]) -> dict[str, Any]:
        return self._provider_data


class FakeDb:
    def __init__(self, provider_data: dict[str, Any]) -> None:
        self.llm_providers = FakeProvidersCollection(provider_data)


class FakeProviderTester(ProviderApiTestMixin):
    def __init__(self, provider_data: dict[str, Any]) -> None:
        self.provider_data = provider_data
        self.connection_args: tuple[str, str, str] | None = None

    async def _get_db(self) -> FakeDb:
        return FakeDb(self.provider_data)

    def _is_valid_api_key(self, _api_key: str) -> bool:
        return False

    def _get_env_api_key(self, _provider_name: str) -> str:
        return "legacy-env-key"

    async def _test_provider_connection(
        self,
        provider_name: str,
        api_key: str,
        display_name: str,
    ) -> dict[str, Any]:
        self.connection_args = (provider_name, api_key, display_name)
        return {"success": True, "message": "ok"}


@pytest.mark.asyncio
async def test_provider_api_uses_catalog_env_key_before_legacy_env(monkeypatch) -> None:
    tester = FakeProviderTester({
        "_id": "dashscope",
        "name": "dashscope",
        "display_name": "DashScope",
        "api_key": "",
    })
    monkeypatch.setattr(tester._provider_catalog, "provider_env_key", lambda _provider: "catalog-env-key")

    result = await tester.test_provider_api("dashscope")

    assert result["success"] is True
    assert tester.connection_args == ("dashscope", "catalog-env-key", "DashScope")


@pytest.mark.asyncio
async def test_provider_base_url_uses_catalog_rules_for_minimax_token_plan() -> None:
    tester = FakeProviderTester({
        "_id": "minimax-token-plan",
        "name": "minimax-token-plan",
        "display_name": "MiniMax Token Plan",
        "default_base_url": "https://api.minimaxi.com/anthropic/",
    })

    assert await tester._provider_base_url("minimax-token-plan") == "https://api.minimaxi.com/anthropic"
