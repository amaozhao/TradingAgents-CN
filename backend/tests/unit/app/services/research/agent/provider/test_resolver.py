from __future__ import annotations

import pytest

from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.provider import resolver as resolver_module
from app.services.research.agent.provider.resolver import (
    AgentModelConfigurationError,
    ProviderCatalog,
    ProviderResolver,
    split_provider_model,
)


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


def _principal() -> ResearchPrincipal:
    return ResearchPrincipal.from_user(USER_A)


def test_provider_catalog_resolves_alias_base_urls() -> None:
    catalog = ProviderCatalog()

    assert catalog.provider_base_url("qwen") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert catalog.provider_base_url("dashscope") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert catalog.provider_base_url("openrouter") == "https://openrouter.ai/api/v1"


def test_provider_catalog_rejects_invalid_minimax_token_plan_url() -> None:
    catalog = ProviderCatalog()

    with pytest.raises(AgentModelConfigurationError, match="必须使用 HTTPS"):
        catalog.provider_base_url("minimax-token-plan", "http://api.minimaxi.com/anthropic")

    with pytest.raises(AgentModelConfigurationError, match="必须指向 /anthropic"):
        catalog.provider_base_url("minimax-token-plan", "https://api.minimaxi.com/v1")


def test_split_provider_model_requires_valid_provider_prefix() -> None:
    assert split_provider_model("openai/gpt-4.1") == ("openai", "gpt-4.1")
    assert split_provider_model("gpt-4.1") == (None, "gpt-4.1")

    with pytest.raises(AgentModelConfigurationError, match="格式无效"):
        split_provider_model("/gpt-4.1")


@pytest.mark.asyncio
async def test_provider_resolver_reports_missing_key_without_fallback(monkeypatch) -> None:
    async def no_user_key(**_kwargs: object) -> None:
        return None

    catalog = ProviderCatalog()
    resolver = ProviderResolver(catalog)
    monkeypatch.setattr(resolver, "default_agent_model", lambda: "openai/gpt-test")
    monkeypatch.setattr(resolver, "fallback_configured_model", lambda: None)
    monkeypatch.setattr(resolver_module.user_model_key_service, "resolve_key_for_agent", no_user_key)
    monkeypatch.setattr(catalog, "provider_env_key", lambda _provider: "")

    with pytest.raises(AgentModelConfigurationError, match="没有有效 API Key"):
        await resolver.resolve_agent_model_config(_principal())
