from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import config as config_router
from app.schemas.config import LLMProviderRequest


class _FakeConfigService:
    def __init__(self, success: bool = True):
        self.success = success
        self.calls = []

    async def update_llm_provider(self, provider_id, update_data):
        self.calls.append((provider_id, update_data))
        return self.success


@pytest.mark.asyncio
async def test_provider_update_persists_valid_api_key(monkeypatch):
    service = _FakeConfigService()
    monkeypatch.setattr(config_router, "config_service", service)

    async def _noop_log_operation(**_kwargs):
        return None

    monkeypatch.setattr(config_router, "log_operation", _noop_log_operation)

    request = LLMProviderRequest(
        name="minimax-token-plan",
        display_name="MiniMax Token Plan",
        api_key="  test-minimax-valid-key-1234567890  ",
    )

    await config_router.update_llm_provider(
        "provider-id", request, SimpleNamespace(id="admin", username="admin")
    )

    assert service.calls[0][1]["api_key"] == "test-minimax-valid-key-1234567890"


@pytest.mark.asyncio
async def test_provider_update_omits_blank_api_key(monkeypatch):
    service = _FakeConfigService()
    monkeypatch.setattr(config_router, "config_service", service)
    monkeypatch.setattr(config_router, "log_operation", lambda **_kwargs: None)

    request = LLMProviderRequest(
        name="minimax-token-plan",
        display_name="MiniMax Token Plan",
        api_key="",
    )

    await config_router.update_llm_provider(
        "provider-id", request, SimpleNamespace(id="admin", username="admin")
    )

    assert "api_key" not in service.calls[0][1]


@pytest.mark.asyncio
async def test_provider_update_rejects_invalid_api_key(monkeypatch):
    service = _FakeConfigService()
    monkeypatch.setattr(config_router, "config_service", service)

    request = LLMProviderRequest(
        name="minimax-token-plan",
        display_name="MiniMax Token Plan",
        api_key="short",
    )

    with pytest.raises(HTTPException) as exc_info:
        await config_router.update_llm_provider(
            "provider-id", request, SimpleNamespace(id="admin", username="admin")
        )

    assert exc_info.value.status_code == 400
    assert service.calls == []
