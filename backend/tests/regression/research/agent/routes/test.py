from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.research import agent as research_agent_router


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
ADMIN = {"id": "admin-a", "username": "root", "is_admin": True, "roles": ["admin"]}


@pytest.mark.asyncio
async def test_capabilities_and_settings_routes_do_not_expose_secrets(monkeypatch):
    async def fake_model_resolution(_principal):
        return {
            "status": "configured",
            "reason": "test",
            "effective_provider": "openai",
            "effective_model": "gpt-test",
            "secrets": "redacted",
            "candidate_models": [],
        }

    monkeypatch.setattr(
        research_agent_router,
        "describe_agent_model_resolution",
        fake_model_resolution,
    )

    capabilities = await research_agent_router.get_research_agent_capabilities(
        current_user=USER
    )
    llm = await research_agent_router.get_research_agent_llm_settings(current_user=USER)
    data_sources = await research_agent_router.get_research_agent_data_source_settings(
        current_user=USER
    )

    assert capabilities["data"]["external_source_runtime"] is False
    assert "/api/research-agent" == capabilities["data"]["namespace"]
    assert llm["data"]["secrets"] == "redacted"
    assert data_sources["data"]["secrets"] == "redacted"


@pytest.mark.asyncio
async def test_settings_mutation_and_shutdown_are_admin_gated_and_disabled():
    with pytest.raises(HTTPException) as llm_exc:
        await research_agent_router.update_research_agent_llm_settings(
            research_agent_router.ResearchSettingsUpdateRequest(values={"model": "x"}),
            current_user=USER,
        )
    admin_llm = await research_agent_router.update_research_agent_llm_settings(
        research_agent_router.ResearchSettingsUpdateRequest(values={"model": "x"}),
        current_user=ADMIN,
    )
    shutdown = await research_agent_router.reject_system_shutdown(current_user=ADMIN)
    run_shutdown = await research_agent_router.reject_run_shutdown(
        "run-1", current_user=ADMIN
    )
    with pytest.raises(HTTPException) as run_shutdown_exc:
        await research_agent_router.reject_run_shutdown("run-1", current_user=USER)

    assert llm_exc.value.status_code == 403
    assert admin_llm["data"]["accepted"] is False
    assert admin_llm["data"]["status"] == "disabled_config_required"
    assert shutdown["data"]["status"] == "intentionally_rejected"
    assert run_shutdown_exc.value.status_code == 403
    assert run_shutdown["data"]["accepted"] is False
    assert run_shutdown["data"]["run_id"] == "run-1"
