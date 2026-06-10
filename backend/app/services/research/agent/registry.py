from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .permissions import ADMIN_CONFIG_WRITE


ToolHandler = Callable[[ToolExecutionContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ResearchTool:
    name: str
    description: str
    permission: str
    schema: dict[str, Any] = field(default_factory=dict)
    handler: ToolHandler | None = None
    enabled: bool = True

    async def run(
        self, context: ToolExecutionContext, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self.permission not in context.principal.permissions:
            raise PermissionError(f"missing permission: {self.permission}")
        if self.handler is None:
            return {"tool": self.name, "accepted": True, "payload": payload}
        return await self.handler(context, payload)


async def _admin_config_write_handler(
    _context: ToolExecutionContext, payload: dict[str, Any]
) -> dict[str, Any]:
    return {"tool": "admin_config_write", "accepted": True, "payload": payload}


class ResearchToolRegistry:
    def __init__(self, tools: Iterable[ResearchTool]):
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def default(cls) -> "ResearchToolRegistry":
        from .tools.analysis import analysis_tools
        from .tools.alpha import alpha_tools
        from .tools.correlation import correlation_tools
        from .tools.coverage import coverage_tools
        from .tools.files import file_tools
        from .tools.goals import goal_tools
        from .tools.journal import journal_tools
        from .tools.live import live_tools
        from .tools.market.data import market_data_tools
        from .tools.memory import memory_tools
        from .tools.multi.factor import multi_factor_tools
        from .tools.quant import quant_tools
        from .tools.reports import report_tools
        from .tools.screening import screening_tools
        from .tools.shadow import shadow_tools
        from .tools.skills import skill_tools
        from .tools.swarm import swarm_tools

        return cls(
            [
                *market_data_tools(),
                *screening_tools(),
                *analysis_tools(),
                *report_tools(),
                *alpha_tools(),
                *correlation_tools(),
                *coverage_tools(),
                *file_tools(),
                *journal_tools(),
                *goal_tools(),
                *swarm_tools(),
                *live_tools(),
                *shadow_tools(),
                *skill_tools(),
                *memory_tools(),
                *multi_factor_tools(),
                *quant_tools(),
                ResearchTool(
                    name="admin_config_write",
                    description="Mutate global admin-owned model configuration.",
                    permission=ADMIN_CONFIG_WRITE,
                    schema={"type": "object", "additionalProperties": True},
                    handler=_admin_config_write_handler,
                ),
            ]
        )

    def all(self) -> list[ResearchTool]:
        return list(self._tools.values())

    def get(self, name: str) -> ResearchTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown research tool: {name}") from exc

    def for_principal(
        self, principal: ResearchPrincipal, *, include_disabled: bool = True
    ) -> list[ResearchTool]:
        return [
            tool
            for tool in self._tools.values()
            if tool.permission in principal.permissions
            and (include_disabled or tool.enabled)
        ]
