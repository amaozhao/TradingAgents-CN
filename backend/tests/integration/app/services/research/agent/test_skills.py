from __future__ import annotations

import pytest

from app.routers.research import agent as research_agent_router
from app.services.research.agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research.agent.registry import ResearchToolRegistry
from app.services.research.agent.skills import ResearchSkillCatalogService


USER = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


def test_skill_catalog_contains_all_source_skill_metadata_without_runtime_dependency():
    skills = ResearchSkillCatalogService().list_skills()

    assert len(skills) == 77
    assert {item["name"] for item in skills} >= {"alpha-zoo", "research-goal", "shadow-account", "web-reader"}
    assert all(item["source_runtime_dependency"] is False for item in skills)
    assert all(item["status"] == "available" for item in skills)


@pytest.mark.asyncio
async def test_skill_route_and_load_skill_tool_use_current_catalog():
    route_response = await research_agent_router.list_research_skills(current_user=USER)
    registry = ResearchToolRegistry.default()
    loaded = await registry.get("load_skill").run(
        ToolExecutionContext(
            principal=ResearchPrincipal.from_user(USER, session_id="session-skills"),
            session_id="session-skills",
        ),
        {"name": "alpha-zoo"},
    )

    assert len(route_response["data"]) == 77
    assert loaded["status"] == "completed"
    assert loaded["skill"]["name"] == "alpha-zoo"
    assert "Do not read from the source project" in loaded["content"]
