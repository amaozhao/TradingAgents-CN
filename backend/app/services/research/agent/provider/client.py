from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.database import get_postgres_db_sync

from ..context import ResearchPrincipal
from ..loop import ModelStreamChunk, ResearchTool


from .resolver import (
    AgentModelConfig,
    ProviderCatalog,
    ProviderResolver,
)
from .resolver import AgentModelConfigurationError as AgentModelConfigurationError  # noqa: F401
from .resolver import settings as settings  # noqa: F401
from .resolver import user_model_key_service as user_model_key_service  # noqa: F401


_provider_catalog = ProviderCatalog()
_provider_resolver = ProviderResolver(_provider_catalog)


async def describe_agent_model_resolution(
    principal: ResearchPrincipal,
) -> dict[str, Any]:
    return await _provider_resolver.describe_agent_model_resolution(principal)


async def resolve_agent_model_config(principal: ResearchPrincipal) -> AgentModelConfig:
    return await _provider_resolver.resolve_agent_model_config(principal)


def _tool_schema(tool: ResearchTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.schema
            or {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }


def _json_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _chat_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    if re.search(r"/chat/completions$", root):
        return root
    return f"{root}/chat/completions"


def _provider_base_url(provider: str, configured_base_url: str = "") -> str:
    return _provider_catalog.provider_base_url(provider, configured_base_url)


def _configured_candidate_models() -> list[tuple[str, str, dict[str, Any]]]:
    catalog = ProviderCatalog(db_sync_loader=get_postgres_db_sync)
    return [
        (candidate.provider, candidate.model, candidate.info)
        for candidate in catalog.configured_candidate_models()
    ]


def _provider_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message.get("role")
    metadata = (
        message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    )
    if role == "assistant" and metadata.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": metadata["tool_calls"],
        }
    if role == "tool":
        payload = {
            "role": "tool",
            "content": message.get("content") or "",
        }
        if metadata.get("tool_call_id"):
            payload["tool_call_id"] = metadata["tool_call_id"]
        if metadata.get("tool_name"):
            payload["name"] = metadata["tool_name"]
        return payload
    if role in {"system", "user", "assistant"}:
        return {"role": role, "content": message.get("content") or ""}
    return {"role": "user", "content": str(message.get("content") or "")}


class OpenAICompatibleModelClient:
    def __init__(self, principal: ResearchPrincipal) -> None:
        self.principal = principal

    async def stream(self, **kwargs: Any) -> AsyncIterator[ModelStreamChunk]:
        config = await resolve_agent_model_config(self.principal)
        prompt = str(kwargs.get("prompt") or "")
        messages = kwargs.get("messages") or []
        tools = kwargs.get("tools") or []
        if _uses_anthropic_messages(config.provider):
            async for chunk in _complete_anthropic_message(
                config=config,
                system_prompt=prompt,
                messages=messages,
                tools=tools,
            ):
                yield chunk
            return

        payload = _chat_payload(
            config=config,
            system_prompt=prompt,
            messages=messages,
            tools=tools,
        )

        emitted_any = False
        try:
            async for chunk in _stream_chat_completion(config, payload):
                emitted_any = True
                yield chunk
            return
        except Exception:
            if emitted_any:
                raise

        async for chunk in _complete_chat_completion(config, payload):
            yield chunk


def _chat_payload(
    *,
    config: AgentModelConfig,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[ResearchTool],
) -> dict[str, Any]:
    provider_messages = [_provider_message(message) for message in messages]
    if system_prompt:
        provider_messages = [
            {"role": "system", "content": system_prompt},
            *provider_messages,
        ]
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": provider_messages,
        "temperature": 0,
    }
    if tools:
        payload["tools"] = [_tool_schema(tool) for tool in tools]
        payload["tool_choice"] = "auto"
    return payload


def _uses_anthropic_messages(provider: str) -> bool:
    return provider.lower() in {"anthropic", "claude", "minimax-token-plan"}


def _anthropic_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    if re.search(r"/v1/messages$", root):
        return root
    return f"{root}/v1/messages"


def _anthropic_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "User-Agent": "tradingagents-cn (python)",
    }


def _anthropic_tool_schema(tool: ResearchTool) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.schema
        or {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }


def _anthropic_message(message: dict[str, Any]) -> dict[str, Any] | None:
    role = message.get("role")
    content = message.get("content") or ""
    metadata = (
        message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    )
    if role == "system":
        return None
    if role == "assistant" and metadata.get("tool_calls"):
        blocks: list[dict[str, Any]] = []
        if content:
            blocks.append({"type": "text", "text": str(content)})
        for tool_call in metadata.get("tool_calls") or []:
            function = (
                tool_call.get("function")
                if isinstance(tool_call.get("function"), dict)
                else {}
            )
            raw_arguments = (
                tool_call.get("arguments")
                if "arguments" in tool_call
                else function.get("arguments")
            )
            blocks.append(
                {
                    "type": "tool_use",
                    "id": str(
                        tool_call.get("id")
                        or tool_call.get("tool_call_id")
                        or tool_call.get("name")
                        or "tool_call"
                    ),
                    "name": str(
                        tool_call.get("name")
                        or tool_call.get("tool_name")
                        or function.get("name")
                        or ""
                    ),
                    "input": raw_arguments
                    if isinstance(raw_arguments, dict)
                    else _json_arguments(raw_arguments),
                }
            )
        return {"role": "assistant", "content": blocks}
    if role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": str(
                        metadata.get("tool_call_id")
                        or metadata.get("id")
                        or metadata.get("tool_name")
                        or "tool_call"
                    ),
                    "content": str(content),
                }
            ],
        }
    if role in {"user", "assistant"}:
        return {"role": role, "content": str(content)}
    return {"role": "user", "content": str(content)}


def _anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        item = _anthropic_message(message)
        if item is not None:
            converted.append(item)
    return converted


def _anthropic_finish_reason(stop_reason: Any) -> str:
    if stop_reason == "tool_use":
        return "tool_calls"
    if stop_reason == "end_turn":
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    return str(stop_reason or "stop")


def _provider_timeout_message(config: AgentModelConfig) -> str:
    return (
        f"Agent LLM request timed out after {config.timeout_seconds:.0f}s "
        f"for {config.provider}/{config.model}"
    )


async def _complete_anthropic_message(
    *,
    config: AgentModelConfig,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[ResearchTool],
) -> AsyncIterator[ModelStreamChunk]:
    payload: dict[str, Any] = {
        "model": config.model,
        "max_tokens": 4096,
        "messages": _anthropic_messages(messages),
    }
    if system_prompt:
        payload["system"] = system_prompt
    if tools:
        payload["tools"] = [_anthropic_tool_schema(tool) for tool in tools]

    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                _anthropic_url(config.base_url),
                headers=_anthropic_headers(config.api_key),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except httpx.TimeoutException as exc:
        raise TimeoutError(_provider_timeout_message(config)) from exc

    for block in body.get("content") or []:
        if block.get("type") == "thinking" and block.get("thinking"):
            yield ModelStreamChunk(reasoning_content=str(block["thinking"]))
        if block.get("type") == "text" and block.get("text"):
            yield ModelStreamChunk(delta=str(block["text"]))
        if block.get("type") == "tool_use" and block.get("name"):
            yield ModelStreamChunk(
                tool_call={
                    "id": block.get("id"),
                    "name": str(block["name"]),
                    "arguments": block.get("input")
                    if isinstance(block.get("input"), dict)
                    else {},
                }
            )
    yield ModelStreamChunk(
        finish_reason=_anthropic_finish_reason(body.get("stop_reason"))
    )


async def _stream_chat_completion(
    config: AgentModelConfig, payload: dict[str, Any]
) -> AsyncIterator[ModelStreamChunk]:
    streaming_payload = {**payload, "stream": True}
    tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason = "stop"

    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            async with client.stream(
                "POST",
                _chat_url(config.base_url),
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=streaming_payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line.split(":", 1)[1].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        body = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    choices = body.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finish_reason = str(choice["finish_reason"])
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield ModelStreamChunk(delta=str(content))
                    reasoning_content = delta.get("reasoning_content") or delta.get(
                        "reasoning"
                    )
                    if reasoning_content:
                        yield ModelStreamChunk(reasoning_content=str(reasoning_content))
                    for tool_delta in delta.get("tool_calls") or []:
                        _merge_tool_call_delta(tool_calls, tool_delta)
    except httpx.TimeoutException as exc:
        raise TimeoutError(_provider_timeout_message(config)) from exc

    for tool_call in _final_tool_calls(tool_calls):
        yield ModelStreamChunk(tool_call=tool_call)
    yield ModelStreamChunk(finish_reason=finish_reason)


def _merge_tool_call_delta(
    tool_calls: dict[int, dict[str, Any]], tool_delta: dict[str, Any]
) -> None:
    index = int(tool_delta.get("index") or 0)
    current = tool_calls.setdefault(
        index,
        {
            "id": None,
            "name": "",
            "arguments": "",
            "thought_signature": None,
        },
    )
    if tool_delta.get("id"):
        current["id"] = tool_delta["id"]
    if signature := _extract_thought_signature(tool_delta):
        current["thought_signature"] = signature
    function = tool_delta.get("function") or {}
    if function.get("name"):
        current["name"] = str(function["name"])
    if function.get("arguments"):
        current["arguments"] = (
            f"{current.get('arguments') or ''}{function['arguments']}"
        )


def _final_tool_calls(tool_calls: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    final: list[dict[str, Any]] = []
    for index in sorted(tool_calls):
        tool_call = tool_calls[index]
        if not tool_call.get("name"):
            continue
        final_call = {
            "id": tool_call.get("id"),
            "name": str(tool_call["name"]),
            "arguments": _json_arguments(tool_call.get("arguments")),
        }
        if tool_call.get("thought_signature"):
            final_call["thought_signature"] = tool_call["thought_signature"]
        final.append(final_call)
    return final


def _extract_thought_signature(tool_call: dict[str, Any]) -> str | None:
    for container in (
        tool_call,
        tool_call.get("function")
        if isinstance(tool_call.get("function"), dict)
        else {},
    ):
        value = container.get("thought_signature") or container.get("thoughtSignature")
        if value:
            return str(value)
    extra_content = tool_call.get("extra_content")
    if isinstance(extra_content, dict):
        google = extra_content.get("google")
        if isinstance(google, dict):
            value = google.get("thought_signature") or google.get("thoughtSignature")
            if value:
                return str(value)
    return None


async def _complete_chat_completion(
    config: AgentModelConfig, payload: dict[str, Any]
) -> AsyncIterator[ModelStreamChunk]:
    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                _chat_url(config.base_url),
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except httpx.TimeoutException as exc:
        raise TimeoutError(_provider_timeout_message(config)) from exc

    choices = body.get("choices") or []
    message = (choices[0].get("message") if choices else {}) or {}
    content = message.get("content") or ""
    if content:
        yield ModelStreamChunk(delta=str(content))
    reasoning_content = message.get("reasoning_content") or message.get("reasoning")
    if reasoning_content:
        yield ModelStreamChunk(reasoning_content=str(reasoning_content))

    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        name = function.get("name")
        if not name:
            continue
        final_call = {
            "id": tool_call.get("id"),
            "name": str(name),
            "arguments": _json_arguments(function.get("arguments")),
        }
        if signature := _extract_thought_signature(tool_call):
            final_call["thought_signature"] = signature
        yield ModelStreamChunk(tool_call=final_call)

    finish_reason = choices[0].get("finish_reason") if choices else "stop"
    yield ModelStreamChunk(finish_reason=str(finish_reason or "stop"))
