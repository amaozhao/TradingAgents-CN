from __future__ import annotations

import copy
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .context import ResearchPrincipal, ToolExecutionContext
from .events import ResearchEventService
from .registry import ResearchTool, ResearchToolRegistry
from .sessions import ResearchSessionService


@dataclass(frozen=True)
class ModelStreamChunk:
    delta: str | None = None
    reasoning_content: str | None = None
    tool_call: dict[str, Any] | None = None
    finish_reason: str | None = None


class ModelClientProtocol:
    async def stream(self, **kwargs: Any) -> AsyncIterator[ModelStreamChunk]:
        raise NotImplementedError


class ResearchAgentCancelled(RuntimeError):
    pass


EMPTY_FINAL_ANSWER_FALLBACK = (
    "本次任务已结束，但模型没有返回最终回答。工具执行记录已保留，请展开执行步骤查看；"
    "如果需要完整结论，请重新发送请求。"
)


def _error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    error_name = exc.__class__.__name__
    if "Timeout" in error_name:
        return f"外部模型或网络服务请求超时（{error_name}）"
    return error_name


def build_research_prompt(
    *, principal: ResearchPrincipal, tools: list[ResearchTool]
) -> str:
    tool_lines = "\n".join(
        f"- {tool.name}: {tool.description}" for tool in sorted(tools, key=lambda t: t.name)
    )
    return (
        "You are the current-project research workspace agent.\n"
        f"Current principal: {principal.role} user {principal.user_id}.\n"
        "Use only the tools listed below. Respect owner-scoped data access, "
        "persisted artifacts, and evidence-backed conclusions.\n"
        "Never call a tool with empty arguments when the user request includes "
        "explicit symbols, dates, text, URLs, factor IDs, or other required inputs. "
        "Pass those inputs through to the matching tool.\n"
        "For requests mentioning 沪深300/HS300/CSI300 plus multi-factor alpha, "
        "momentum/reversal/volatility/turnover, IC weighting, or 2023-2024 backtests, "
        "call multi_factor_alpha_backtest with the requested universe, factors, and dates "
        "before writing the final answer.\n"
        "Available tools:\n"
        f"{tool_lines}\n"
    )


def _extract_symbols_from_text(text: str) -> list[str]:
    match = re.search(
        r"\bsymbols?\s+(.+?)(?:\s+from\b|\s+between\b|\s+for\s+the\s+period\b|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = match.group(1) if match else text
    tokens = re.findall(
        r"\b(?:SH|SZ|BJ)?\d{6}(?:\.(?:SH|SZ|BJ))?\b|\b[A-Z]{1,8}(?:[-/](?:USD|USDT))?\b",
        source.upper(),
    )
    ignored = {"CREATE", "STYLE", "BACKTEST", "FROM", "SHOW", "USE", "THEN", "AND", "FOR"}
    symbols: list[str] = []
    for token in tokens:
        if token in ignored:
            continue
        if token not in symbols:
            symbols.append(token)
    return symbols


def _infer_empty_tool_arguments(
    tool_call: dict[str, Any], *, user_message: str
) -> dict[str, Any]:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict) and arguments:
        return tool_call
    if str(tool_call.get("name") or "") != "backtest":
        return tool_call

    symbols = _extract_symbols_from_text(user_message)
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", user_message)
    inferred: dict[str, Any] = {}
    if symbols:
        inferred["symbols"] = symbols
    if len(dates) >= 1:
        inferred["start_date"] = dates[0]
    if len(dates) >= 2:
        inferred["end_date"] = dates[1]
    if re.search(r"risk[-\s]?parity|inverse[-\s]?vol", user_message, flags=re.IGNORECASE):
        inferred["strategy"] = "risk_parity"
    return {**tool_call, "arguments": inferred} if inferred else tool_call


class ResearchAgentLoop:
    def __init__(
        self,
        *,
        model_client: ModelClientProtocol,
        registry: ResearchToolRegistry | None = None,
        session_service: ResearchSessionService | None = None,
        event_service: ResearchEventService | None = None,
        max_length_continuations: int = 1,
        max_tool_iterations: int = 8,
        context_char_budget: int = 40_000,
        preserve_recent_messages: int = 6,
        cancel_checker: Callable[[], Awaitable[bool]] | None = None,
        emit_terminal_event: bool = True,
    ):
        self.model_client = model_client
        self.registry = registry or ResearchToolRegistry.default()
        self.session_service = session_service or ResearchSessionService()
        self.event_service = event_service or ResearchEventService()
        self.max_length_continuations = max_length_continuations
        self.max_tool_iterations = max_tool_iterations
        self.context_char_budget = context_char_budget
        self.preserve_recent_messages = preserve_recent_messages
        self.cancel_checker = cancel_checker
        self.emit_terminal_event = emit_terminal_event

    async def _is_cancelled(self) -> bool:
        return bool(self.cancel_checker and await self.cancel_checker())

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
        linked_attempt_id: str | None = None,
    ) -> dict[str, Any]:
        message = await self.session_service.append_message(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            metadata=metadata or {},
            linked_attempt_id=linked_attempt_id,
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
            error_message = _error_message(exc)
            result = {
                "tool": tool_name,
                "status": "error",
                "accepted": False,
                "error": error_message,
                "instruction": (
                    "The tool call failed. Continue with available evidence, "
                    "or call the same tool again only if you can provide the missing inputs."
                ),
            }
            await self._append_event(
                session_id=str(context.session_id),
                user_id=context.principal.user_id,
                event_type="tool_failed",
                payload={"tool_name": tool_name, "error": error_message, "result": result},
            )

        await self._append_message(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            role="tool",
            content=json.dumps(result, ensure_ascii=False, default=str),
            metadata={
                "tool_name": tool_name,
                "tool_call_id": tool_call.get("id"),
            },
            linked_attempt_id=context.request_id,
        )
        completed_payload: dict[str, Any] = {
            "tool_name": tool_name,
            "result": result,
        }
        artifact_id = result.get("artifact_id")
        if not artifact_id and isinstance(result.get("result"), dict):
            artifact_id = result["result"].get("artifact_id")
        if artifact_id:
            completed_payload["artifact_id"] = artifact_id
        await self._append_event(
            session_id=str(context.session_id),
            user_id=context.principal.user_id,
            event_type="tool_completed",
            payload=completed_payload,
        )
        return result

    async def _force_final_answer(
        self,
        *,
        prompt: str,
        session_id: str,
        principal: ResearchPrincipal,
        attempt_id: str | None,
        content_parts: list[str],
        reasoning_parts: list[str],
        continuation_count: int,
    ) -> str:
        raw_messages = await self.session_service.list_messages(
            session_id, principal.user_id
        )
        context_messages, compact_payload = compact_messages_for_context(
            raw_messages,
            char_budget=self.context_char_budget,
            preserve_recent=self.preserve_recent_messages,
        )
        if compact_payload:
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="compact",
                payload={**compact_payload, "attempt_id": attempt_id},
            )
        context_messages = [
            *context_messages,
            {
                "role": "user",
                "content": (
                    "工具调用预算已经用尽。不要再调用任何工具。请只基于当前会话中已经"
                    "返回的工具结果和受限信息，直接输出最终中文结论。若 Web 搜索、"
                    "行情或分析工具受限，必须明确说明证据缺口，不要编造外部事实。"
                ),
            },
        ]
        final_finish_reason = "tool_iteration_limit"
        async for chunk in self.model_client.stream(
            prompt=f"{prompt}\nDo not call tools in the finalization round.",
            session_id=session_id,
            messages=context_messages,
            tools=[],
            continuation_count=continuation_count,
        ):
            if chunk.delta:
                content_parts.append(chunk.delta)
                await self._append_event(
                    session_id=session_id,
                    user_id=principal.user_id,
                    event_type="assistant_delta",
                    payload={
                        "text": chunk.delta,
                        "content": chunk.delta,
                        "attempt_id": attempt_id,
                    },
                )
            if chunk.reasoning_content:
                reasoning_parts.append(chunk.reasoning_content)
                await self._append_event(
                    session_id=session_id,
                    user_id=principal.user_id,
                    event_type="log",
                    payload={
                        "kind": "reasoning",
                        "content": chunk.reasoning_content,
                        "attempt_id": attempt_id,
                    },
                )
            if chunk.finish_reason:
                final_finish_reason = f"tool_iteration_limit:{chunk.finish_reason}"
        return final_finish_reason

    async def run(
        self,
        *,
        principal: ResearchPrincipal,
        session_id: str,
        user_message: str,
        attempt_id: str | None = None,
        persist_user_message: bool = True,
    ) -> dict[str, Any]:
        if not await self.session_service.get_session(session_id, principal.user_id):
            raise PermissionError("research session is not available to this principal")

        available_tools = self.registry.for_principal(principal, include_disabled=False)
        prompt = build_research_prompt(principal=principal, tools=available_tools)
        context = ToolExecutionContext(
            principal=principal,
            session_id=session_id,
            request_id=attempt_id,
        )

        if persist_user_message:
            await self._append_message(
                session_id=session_id,
                user_id=principal.user_id,
                role="user",
                content=user_message,
                linked_attempt_id=attempt_id,
            )

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        linked_artifact_ids: list[str] = []
        linked_task_ids: list[str] = []
        continuation_count = 0
        tool_iteration_count = 0
        used_tool_call = False
        forced_final_answer = False
        finish_reason: str | None = None

        try:
            while True:
                if await self._is_cancelled():
                    await self._append_event(
                        session_id=session_id,
                        user_id=principal.user_id,
                        event_type="task_failed",
                        payload={"status": "cancelled", "attempt_id": attempt_id},
                    )
                    raise ResearchAgentCancelled("research attempt cancelled")
                finish_reason = None
                had_tool_call = False
                round_content_start = len(content_parts)
                raw_messages = await self.session_service.list_messages(
                    session_id, principal.user_id
                )
                context_messages, compact_payload = compact_messages_for_context(
                    raw_messages,
                    char_budget=self.context_char_budget,
                    preserve_recent=self.preserve_recent_messages,
                )
                if compact_payload:
                    await self._append_event(
                        session_id=session_id,
                        user_id=principal.user_id,
                        event_type="compact",
                        payload={**compact_payload, "attempt_id": attempt_id},
                    )
                async for chunk in self.model_client.stream(
                    prompt=prompt,
                    session_id=session_id,
                    messages=context_messages,
                    tools=available_tools,
                    continuation_count=continuation_count,
                ):
                    if await self._is_cancelled():
                        await self._append_event(
                            session_id=session_id,
                            user_id=principal.user_id,
                            event_type="task_failed",
                            payload={"status": "cancelled", "attempt_id": attempt_id},
                        )
                        raise ResearchAgentCancelled("research attempt cancelled")
                    if chunk.delta:
                        content_parts.append(chunk.delta)
                        await self._append_event(
                            session_id=session_id,
                            user_id=principal.user_id,
                            event_type="assistant_delta",
                            payload={
                                "text": chunk.delta,
                                "content": chunk.delta,
                                "attempt_id": attempt_id,
                            },
                        )
                    if chunk.reasoning_content:
                        reasoning_parts.append(chunk.reasoning_content)
                        await self._append_event(
                            session_id=session_id,
                            user_id=principal.user_id,
                            event_type="log",
                            payload={
                                "kind": "reasoning",
                                "content": chunk.reasoning_content,
                                "attempt_id": attempt_id,
                            },
                        )
                    if chunk.tool_call:
                        tool_call = _infer_empty_tool_arguments(
                            chunk.tool_call,
                            user_message=user_message,
                        )
                        if await self._is_cancelled():
                            await self._append_event(
                                session_id=session_id,
                                user_id=principal.user_id,
                                event_type="task_failed",
                                payload={"status": "cancelled", "attempt_id": attempt_id},
                            )
                            raise ResearchAgentCancelled("research attempt cancelled")
                        had_tool_call = True
                        used_tool_call = True
                        await self._append_message(
                            session_id=session_id,
                            user_id=principal.user_id,
                            role="assistant",
                            content="",
                            metadata={
                                "finish_reason": "tool_calls",
                                "tool_calls": [
                                    {
                                        "id": chunk.tool_call.get("id"),
                                        "type": "function",
                                        "function": {
                                            "name": tool_call.get("name"),
                                            "arguments": json.dumps(
                                                tool_call.get("arguments") or {},
                                                ensure_ascii=False,
                                            ),
                                        },
                                        **(
                                            {
                                                "extra_content": {
                                                    "google": {
                                                        "thought_signature": chunk.tool_call[
                                                            "thought_signature"
                                                        ]
                                                    }
                                                }
                                            }
                                            if chunk.tool_call.get("thought_signature")
                                            else {}
                                        ),
                                    }
                                ],
                                "attempt_id": attempt_id,
                                "reasoning_content": "".join(reasoning_parts),
                            },
                            linked_attempt_id=attempt_id,
                        )
                        tool_result = await self._run_tool(
                            tool_call=tool_call, context=context
                        )
                        artifact_id = tool_result.get("artifact_id")
                        if not artifact_id and isinstance(tool_result.get("result"), dict):
                            artifact_id = tool_result["result"].get("artifact_id")
                        if artifact_id and str(artifact_id) not in linked_artifact_ids:
                            linked_artifact_ids.append(str(artifact_id))
                        task_id = tool_result.get("task_id") or tool_result.get("job_id")
                        if task_id and str(task_id) not in linked_task_ids:
                            linked_task_ids.append(str(task_id))
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason

                should_continue_for_tool = had_tool_call and (
                    finish_reason in {"tool_calls", "function_call"}
                    or len(content_parts) == round_content_start
                )
                if should_continue_for_tool:
                    tool_iteration_count += 1
                    if tool_iteration_count >= self.max_tool_iterations:
                        finish_reason = "tool_iteration_limit"
                        finish_reason = await self._force_final_answer(
                            prompt=prompt,
                            session_id=session_id,
                            principal=principal,
                            attempt_id=attempt_id,
                            content_parts=content_parts,
                            reasoning_parts=reasoning_parts,
                            continuation_count=continuation_count,
                        )
                        forced_final_answer = True
                        break
                    continue

                if (
                    finish_reason == "length"
                    and continuation_count < self.max_length_continuations
                ):
                    continuation_count += 1
                    continue
                break

            final_content = "".join(content_parts)
            if not final_content.strip() and used_tool_call and not forced_final_answer:
                finish_reason = await self._force_final_answer(
                    prompt=prompt,
                    session_id=session_id,
                    principal=principal,
                    attempt_id=attempt_id,
                    content_parts=content_parts,
                    reasoning_parts=reasoning_parts,
                    continuation_count=continuation_count,
                )
                final_content = "".join(content_parts)
                forced_final_answer = True
            if not final_content.strip():
                final_content = EMPTY_FINAL_ANSWER_FALLBACK
                content_parts.append(final_content)
                await self._append_event(
                    session_id=session_id,
                    user_id=principal.user_id,
                    event_type="assistant_delta",
                    payload={
                        "text": final_content,
                        "content": final_content,
                        "attempt_id": attempt_id,
                    },
                )
            reasoning_content = "".join(reasoning_parts)
            assistant_message = await self._append_message(
                session_id=session_id,
                user_id=principal.user_id,
                role="assistant",
                content=final_content,
                metadata={
                    "finish_reason": finish_reason,
                    "continuations": continuation_count,
                    "artifact_ids": linked_artifact_ids,
                    "task_ids": linked_task_ids,
                    "attempt_id": attempt_id,
                    "reasoning_content": reasoning_content,
                },
                linked_attempt_id=attempt_id,
            )
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="message_completed",
                payload={
                    "message_id": assistant_message["message_id"],
                    "content": final_content,
                    "artifact_ids": linked_artifact_ids,
                    "task_ids": linked_task_ids,
                    "attempt_id": attempt_id,
                },
            )
            if self.emit_terminal_event:
                await self._append_event(
                    session_id=session_id,
                    user_id=principal.user_id,
                    event_type="task_completed",
                    payload={
                        "finish_reason": finish_reason,
                        "artifact_ids": linked_artifact_ids,
                        "task_ids": linked_task_ids,
                        "attempt_id": attempt_id,
                    },
                )
            return {
                "content": final_content,
                "message_id": assistant_message["message_id"],
                "finish_reason": finish_reason,
                "continuations": continuation_count,
                "artifact_ids": linked_artifact_ids,
                "task_ids": linked_task_ids,
            }
        except Exception as exc:
            await self._append_event(
                session_id=session_id,
                user_id=principal.user_id,
                event_type="task_failed",
                payload={"error": _error_message(exc)},
            )
            raise


def _message_chars(messages: list[dict[str, Any]]) -> int:
    return len(json.dumps(messages, ensure_ascii=False, default=str))


def compact_messages_for_context(
    messages: list[dict[str, Any]],
    *,
    char_budget: int = 40_000,
    preserve_recent: int = 6,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    original_chars = _message_chars(messages)
    if original_chars <= char_budget:
        return messages, None

    compacted = copy.deepcopy(messages)
    preserved_start = max(0, len(compacted) - max(1, preserve_recent))
    cleared_tool_results = 0
    collapsed_messages = 0

    for index, message in enumerate(compacted):
        if index >= preserved_start:
            continue
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, str) and len(content) > 120:
            message["content"] = "[cleared old tool result during context compaction]"
            cleared_tool_results += 1
            continue
        if isinstance(content, str) and len(content) > 1200:
            head = content[:500]
            tail = content[-300:]
            omitted = len(content) - len(head) - len(tail)
            message["content"] = (
                f"{head}\n\n...[{omitted} chars compacted for context budget]...\n\n{tail}"
            )
            collapsed_messages += 1

    compacted_chars = _message_chars(compacted)
    if compacted_chars > char_budget and len(compacted) > preserve_recent:
        first_message = compacted[0:1]
        recent_messages = compacted[-preserve_recent:]
        omitted_count = len(compacted) - len(first_message) - len(recent_messages)
        compacted = [
            *first_message,
            {
                "role": "system",
                "content": f"[{omitted_count} older messages compacted for context budget]",
                "metadata": {"compact": True, "omitted_messages": omitted_count},
            },
            *recent_messages,
        ]
        compacted_chars = _message_chars(compacted)

    return compacted, {
        "original_chars": original_chars,
        "compacted_chars": compacted_chars,
        "cleared_tool_results": cleared_tool_results,
        "collapsed_messages": collapsed_messages,
    }
