from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import config as config_router
from app.schemas.config import LLMConfigRequest, LLMProviderRequest


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
ADMIN = {"id": "admin", "username": "admin", "is_admin": True, "roles": ["admin"]}


class FakeConfigService:
    def __init__(self):
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def delete_llm_config(self, provider: str, model_name: str) -> bool:
        self.calls.append(("delete_llm_config", (provider, model_name)))
        return True

    async def set_default_llm(self, name: str) -> bool:
        self.calls.append(("set_default_llm", (name,)))
        return True

    async def add_llm_provider(self, provider) -> str:
        self.calls.append(("add_llm_provider", (provider.name,)))
        return "provider-id"

    async def update_llm_provider(self, provider_id: str, update_data: dict[str, Any]):
        self.calls.append(("update_llm_provider", (provider_id, update_data)))
        return True

    async def delete_llm_provider(self, provider_id: str) -> bool:
        self.calls.append(("delete_llm_provider", (provider_id,)))
        return True

    async def toggle_llm_provider(self, provider_id: str, is_active: bool) -> bool:
        self.calls.append(("toggle_llm_provider", (provider_id, is_active)))
        return True

    async def fetch_provider_models(self, provider_id: str, filters):
        self.calls.append(("fetch_provider_models", (provider_id, filters)))
        return {"success": True, "models": [], "message": "获取模型列表成功"}

    async def migrate_env_to_providers(self):
        self.calls.append(("migrate_env_to_providers", ()))
        return {
            "success": True,
            "message": "迁移完成",
            "migrated_count": 1,
            "skipped_count": 0,
        }

    async def update_llm_config(self, llm_config) -> bool:
        self.calls.append(("update_llm_config", (llm_config.provider, llm_config.model_name)))
        return True


async def _noop_log_operation(**_kwargs):
    return None


ConfigCall = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _provider_request() -> LLMProviderRequest:
    return LLMProviderRequest(name="minimax-token-plan", display_name="MiniMax Token Plan")


def _llm_config_request() -> LLMConfigRequest:
    return LLMConfigRequest(
        provider="minimax-token-plan",
        model_name="MiniMax-Text-01",
        api_key="test-valid-api-key-1234567890",
    )


def _admin_cases() -> list[tuple[str, ConfigCall]]:
    return [
        (
            "delete_llm_config",
            lambda user: config_router.delete_llm_config(
                "minimax-token-plan", "MiniMax-Text-01", current_user=user
            ),
        ),
        (
            "set_default_llm_legacy",
            lambda user: config_router.set_default_llm_legacy(
                config_router.SetDefaultRequest(name="MiniMax-Text-01"),
                current_user=user,
            ),
        ),
        (
            "add_llm_provider",
            lambda user: config_router.add_llm_provider(
                _provider_request(), current_user=user
            ),
        ),
        (
            "update_llm_provider",
            lambda user: config_router.update_llm_provider(
                "provider-id", _provider_request(), current_user=user
            ),
        ),
        (
            "delete_llm_provider",
            lambda user: config_router.delete_llm_provider(
                "provider-id", current_user=user
            ),
        ),
        (
            "toggle_llm_provider",
            lambda user: config_router.toggle_llm_provider(
                "provider-id",
                config_router.ToggleProviderRequest(is_active=False),
                current_user=user,
            ),
        ),
        (
            "fetch_provider_models",
            lambda user: config_router.fetch_provider_models(
                "provider-id",
                config_router.FetchProviderModelsRequest(limit=5),
                current_user=user,
            ),
        ),
        (
            "migrate_env_to_providers",
            lambda user: config_router.migrate_env_to_providers(current_user=user),
        ),
        (
            "add_llm_config_compat",
            lambda user: config_router.add_llm_config(
                _llm_config_request(), current_user=user
            ),
        ),
        (
            "set_default_llm_compat",
            lambda user: config_router.set_default_llm(
                config_router.SetDefaultRequest(name="MiniMax-Text-01"),
                current_user=user,
            ),
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,call", _admin_cases())
async def test_non_admin_cannot_mutate_global_llm_config(
    monkeypatch, case_name: str, call: ConfigCall
):
    service = FakeConfigService()
    monkeypatch.setattr(config_router, "config_service", service)
    monkeypatch.setattr(config_router, "log_operation", _noop_log_operation)

    with pytest.raises(HTTPException) as exc:
        await call(USER_A)

    assert case_name
    assert exc.value.status_code == 403
    assert service.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,call", _admin_cases())
async def test_admin_can_mutate_global_llm_config(
    monkeypatch, case_name: str, call: ConfigCall
):
    service = FakeConfigService()
    monkeypatch.setattr(config_router, "config_service", service)
    monkeypatch.setattr(config_router, "log_operation", _noop_log_operation)

    response = await call(ADMIN)

    assert case_name
    assert response["success"] is True
    assert service.calls
