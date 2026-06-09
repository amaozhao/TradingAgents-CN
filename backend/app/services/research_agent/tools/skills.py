from __future__ import annotations

from typing import Any

from app.services.research_agent.skills import ResearchSkillCatalogService

from ..context import ToolExecutionContext
from ..permissions import SKILL_READ
from ..registry import ResearchTool


async def _load_skill(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    name = str(payload.get("name") or payload.get("skill") or "").strip().lower()
    if not name:
        raise ValueError("name is required")
    skill = ResearchSkillCatalogService().get_skill(name)
    if not skill:
        return {"tool": "load_skill", "status": "not_found", "name": name}
    return {
        "tool": "load_skill",
        "status": "completed",
        "skill": skill,
        "content": skill["prompt_context"],
    }


def skill_tools() -> list[ResearchTool]:
    return [
        ResearchTool(
            name="load_skill",
            description="Load current-project skill metadata into the Agent context without reading source-project files.",
            permission=SKILL_READ,
            schema={
                "type": "object",
                "properties": {"name": {"type": "string"}, "skill": {"type": "string"}},
                "required": ["name"],
            },
            handler=_load_skill,
        )
    ]
