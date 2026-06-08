from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .events import ResearchEventService
from .registry import ResearchTool, ResearchToolRegistry
from .sessions import ResearchSessionService


@dataclass(frozen=True)
class ModelStreamChunk:
    delta: str | None = None
    tool_call: dict[str, Any] | None = None
    finish_reason: str | None = None


class ModelClientProtocol:
    async def stream(self, **kwargs: Any) -> AsyncIterator[ModelStreamChunk]:
        raise NotImplementedError


def build_research_prompt(
    *, principal: ResearchPrincipal, tools: list[ResearchTool]
) -> str:
    tool_lines = "\n".join(
        f"- {tool.name}: {tool.description}" for tool in sorted(tools, key=lambda t: t.name)
    )
    return (
        "You are the TradingAgents-CN research workspace agent.\n"
        f"Current principal: {principal.role} user {principal.user_id}.\n"
        "Use only the tools listed below. Respect owner-scoped data access, "
        "persisted artifacts, and evidence-backed conclusions.\n"
        "Available tools:\n"
        f"{tool_lines}\n"
    )


class ResearchAgentLoop:
    def __init__(
        self,
        *,
        model_client: ModelClientProtocol,
        registry: ResearchToolRegistry | None = None,
        session_service: ResearchSessionService | None = None,
        event_service: ResearchEventService | None = None,
        max_length_continuations: int = 1,
    ):
        self.model_client = model_client
        self.registry = registry or ResearchToolRegistry.default()
        self.session_service = session_service or ResearchSessionService()
        self.event_service = event_service or ResearchEventService()
        self.max_length_continuations = max_length_continuations

    async def _append_event(
        self,
        *,
        session_id: str,
        user_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.event_service.append(
            session_id=session_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload or {},
        )

    async def _append_message(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message = await self.session_service.append_message(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        if message is None:
            raise PermissionError("research session is not available to this principal")
        return message

    async def _run_tool(
        self,
        *,
        tool_call: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        tool_name = str(tool_call.get("name") or "")
        arguments = tool_call.get("arguments") or {}
        tool = self.registry.get(tool_name)
        await self._append_event(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            event_type="tool_started",
            payload={"tool_name": tool_name, "arguments": arguments},
        )
        try:
            result = await tool.run(context, arguments)
        except Exception as exc:
            await self._append_event(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                event_type="tool_failed",
                payload={"tool_name": tool_name, "error": str(exc)},
            )
            raise

        await self._append_message(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            role="tool",
            content=json.dumps(result, ensure_ascii=False),
            metadata={"tool_name": tool_name},
        )
        await self._append_event(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            event_type="tool_completed",
            payload={"tool_name": tool_name, "result": result},
        )
        return result

    async def run(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        if not await self.session_service.get_session(session_id, principal.user_id):
            raise PermissionError("research session is not available to this principal")

        available_tools = self.registry.for_principal(principal)
        prompt = build_research_prompt(principal=principal, tools=available_tools)
        context = ToolExecutionContext(principal=principal, session_id=session_id)

        await self._append_message(
            session_id=session_id,
            user_id=principal.user_id,
            role="user",
            content=user_message,
        )

        content_parts: list[str] = []
        continuation_count = 0
        finish_reason: str | None = None

        try:
            while True:
                finish_reason = None
                async for chunk in self.model_client.stream(
                    prompt=prompt,
                    session_id=session_id,
                    messages=await self.session_service.list_messages(
                        session_id, principal.user_id
                    ),
                    tools=available_tools,
                    continuation_count=continuation_count,
                ):
                    if chunk.delta:
                        content_parts.append(chunk.delta)
                        await self._append_event(
                            session_id=session_id,
                            user_id=principal.user_id,
                            event_type="assistant_delta",
                            payload={"text": chunk.delta},
                        )
                    if chunk.tool_call:
                        await self._run_tool(tool_call=chunk.tool_call, context=context)
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason

                if (
                    finish_reason == "length"
                    and continuation_count < self.max_length_continuations
                ):
                    continuation_count += 1
                    continue
                break

            final_content = "".join(content_parts)
            assistant_message = await self._append_message(
                session_id=session_id,
                user_id=principal.user_id,
                role="assistant",
                content=final_content,
                metadata={
                    "finish_reason": finish_reason,
                    "continuations": continuation_count,
                },
            )
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="message_completed",
                payload={"message_id": assistant_message["message_id"]},
            )
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_completed",
                payload={"finish_reason": finish_reason},
            )
            return {
                "content": final_content,
                "message_id": assistant_message["message_id"],
                "finish_reason": finish_reason,
                "continuations": continuation_count,
            }
        except Exception as exc:
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_failed",
                payload={"error": str(exc)},
            )
            raise
