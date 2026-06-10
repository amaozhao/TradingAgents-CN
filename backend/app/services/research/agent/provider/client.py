from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.bridge import get_bridged_api_key, get_bridged_model
from app.core.config import settings
from app.core.database import get_postgres_db_sync
from app.core.unified import unified_config
from app.services.analysis.simple.provider import get_provider_and_url_by_model_sync

from ..context import ResearchPrincipal
from ..loop import ModelStreamChunk, ResearchTool
from ..user.model.keys import user_model_key_service


class AgentModelConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentModelConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 300.0


def _is_placeholder(value: str | None) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    return (
        lowered == "your-api-key"
        or lowered.startswith("your_")
        or lowered.startswith("your-")
        or lowered.endswith("_here")
        or lowered.endswith("-here")
        or len(cleaned) <= 10
    )


def _first_configured_text(*values: str | None) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and not _is_placeholder(cleaned):
            return cleaned
    return ""


def _first_configured_model_text(*values: str | None) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        lowered = cleaned.lower()
        if (
            cleaned
            and lowered != "your-api-key"
            and not lowered.startswith("your_")
            and not lowered.startswith("your-")
            and not lowered.endswith("_here")
            and not lowered.endswith("-here")
        ):
            return cleaned
    return ""


def _default_agent_model() -> str:
    return _first_configured_model_text(
        settings.TRADING_AGENTS_DEFAULT_MODEL,
        get_bridged_model("default"),
        settings.TRADING_AGENTS_QUICK_MODEL,
        get_bridged_model("quick"),
        unified_config.get_default_model(),
        unified_config.get_quick_analysis_model(),
    )


def _split_provider_model(value: str) -> tuple[str | None, str]:
    cleaned = value.strip()
    if "/" in cleaned:
        provider, model = cleaned.split("/", 1)
        provider = provider.strip().lower()
        model = model.strip()
    else:
        provider = None
        model = cleaned
    if not model or (provider is not None and not provider):
        raise AgentModelConfigurationError("Agent 默认模型格式无效，应为 provider/model")
    return provider, model


def _minimax_token_plan_base_url(configured_base_url: str = "") -> str:
    base_url = str(configured_base_url or "https://api.minimaxi.com/anthropic").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise AgentModelConfigurationError("MiniMax Token Plan base URL 必须使用 HTTPS")
    if parsed.hostname not in {"api.minimaxi.com", "api.minimax.io"}:
        raise AgentModelConfigurationError("MiniMax Token Plan base URL 仅允许 api.minimaxi.com 或 api.minimax.io")
    if not parsed.path.startswith("/anthropic"):
        raise AgentModelConfigurationError("MiniMax Token Plan base URL 必须指向 /anthropic 路径")
    return base_url


def _provider_base_url(provider: str, configured_base_url: str = "") -> str:
    provider = provider.lower()
    if provider == "minimax-token-plan":
        return _minimax_token_plan_base_url(configured_base_url)
    if configured_base_url:
        return configured_base_url.rstrip("/")
    if provider == "openai":
        return (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    if provider == "deepseek":
        return (settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip("/")
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    if provider in {"dashscope", "qwen"}:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    if provider == "minimax":
        return "https://api.minimax.io/v1"
    if provider in {"anthropic", "claude"}:
        return "https://api.anthropic.com"
    if provider == "custom":
        return settings.CUSTOM_OPENAI_BASE_URL.rstrip("/")
    raise AgentModelConfigurationError(f"不支持的 Agent 模型提供方: {provider}")


def _candidate_backend_url(
    provider: str,
    configured_base_url: str = "",
    provider_default_base_url: str = "",
) -> str:
    provider = provider.lower()
    configured = str(configured_base_url or "").strip()
    provider_default = str(provider_default_base_url or "").strip()
    if provider != "minimax-token-plan":
        return configured or provider_default
    if configured:
        try:
            return _minimax_token_plan_base_url(configured)
        except AgentModelConfigurationError:
            if provider_default:
                return provider_default
            raise
    return provider_default


def _provider_env_key(provider: str) -> str:
    provider = provider.lower()
    bridged_key = get_bridged_api_key(provider)
    if not bridged_key and provider in {"dashscope", "qwen"}:
        bridged_key = get_bridged_api_key("dashscope") or get_bridged_api_key("qwen")
    if not _is_placeholder(bridged_key):
        return str(bridged_key)
    if provider == "minimax-token-plan":
        return settings.text_value("MINIMAX_TOKEN_PLAN_API_KEY")
    if provider == "minimax":
        return settings.text_value("MINIMAX_API_KEY")
    if provider in {"anthropic", "claude"}:
        return "" if _is_placeholder(settings.ANTHROPIC_API_KEY) else settings.ANTHROPIC_API_KEY
    if provider == "openai":
        return "" if _is_placeholder(settings.OPENAI_API_KEY) else settings.OPENAI_API_KEY
    if provider == "deepseek":
        return "" if _is_placeholder(settings.DEEPSEEK_API_KEY) else settings.DEEPSEEK_API_KEY
    if provider == "openrouter":
        return "" if _is_placeholder(settings.OPENROUTER_API_KEY) else settings.OPENROUTER_API_KEY
    if provider in {"dashscope", "qwen"}:
        return "" if _is_placeholder(settings.DASHSCOPE_API_KEY) else settings.DASHSCOPE_API_KEY
    if provider == "custom":
        return "" if _is_placeholder(settings.CUSTOM_OPENAI_API_KEY) else settings.CUSTOM_OPENAI_API_KEY
    return ""


def _configured_candidate_models() -> list[tuple[str, str, dict[str, Any]]]:
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    try:
        db = get_postgres_db_sync()
        system = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)]) or {}
        providers = {
            str(item.get("name") or "").strip().lower(): item
            for item in db.llm_providers.find({})
        }
        for item in system.get("llm_configs", []):
            if not item.get("enabled"):
                continue
            model = str(item.get("model_name") or "").strip()
            provider = str(item.get("provider") or "").strip().lower()
            if not model or not provider:
                continue
            key = (provider, model)
            if key in seen:
                continue
            seen.add(key)
            provider_doc = providers.get(provider) or providers.get(
                "qwen" if provider == "dashscope" else provider
            )
            candidates.append((
                provider,
                model,
                {
                    "provider": provider,
                    "api_key": item.get("api_key") or (provider_doc or {}).get("api_key") or "",
                    "backend_url": _candidate_backend_url(
                        provider,
                        str(item.get("api_base") or ""),
                        str((provider_doc or {}).get("default_base_url") or ""),
                    ),
                },
            ))

        minimax_provider = providers.get("minimax-token-plan")
        if minimax_provider and ("minimax-token-plan", "MiniMax-M3") not in seen:
            minimax_key = minimax_provider.get("api_key") or _provider_env_key("minimax-token-plan")
            candidates.append((
                "minimax-token-plan",
                "MiniMax-M3",
                {
                    "provider": "minimax-token-plan",
                    "api_key": minimax_key,
                    "backend_url": minimax_provider.get("default_base_url") or "",
                },
            ))
    except Exception:
        return candidates
    return candidates


def _fallback_configured_model() -> tuple[str, str, dict[str, Any]] | None:
    for provider, model, info in _configured_candidate_models():
        api_key = _first_configured_text(str(info.get("api_key") or ""), _provider_env_key(provider))
        if api_key:
            return provider, model, {**info, "api_key": api_key}
    return None


def _safe_provider_model(value: str) -> tuple[str, str]:
    try:
        provider, model = _split_provider_model(value)
        if provider is None:
            provider_info = get_provider_and_url_by_model_sync(model)
            provider = str(provider_info.get("provider") or "").strip().lower()
        return provider or "", model
    except Exception:
        return "", value


async def describe_agent_model_resolution(principal: ResearchPrincipal) -> dict[str, Any]:
    """Return redacted Agent model diagnostics for UI/settings surfaces."""
    default_model = _default_agent_model()
    default_provider = ""
    default_model_name = ""
    default_has_key = False
    default_error = ""
    if default_model:
        default_provider, default_model_name = _safe_provider_model(default_model)
        if default_provider:
            try:
                provider_info = (
                    get_provider_and_url_by_model_sync(default_model_name)
                    if "/" not in default_model
                    else {}
                )
                user_key = await user_model_key_service.resolve_key_for_agent(
                    user_id=principal.user_id,
                    provider=default_provider,
                    model=default_model_name,
                )
                default_has_key = bool(
                    _first_configured_text(
                        user_key,
                        str(provider_info.get("api_key") or ""),
                        _provider_env_key(default_provider),
                    )
                )
            except Exception as exc:
                default_error = str(exc)

    candidates = []
    for provider, model, info in _configured_candidate_models():
        has_key = bool(_first_configured_text(str(info.get("api_key") or ""), _provider_env_key(provider)))
        candidates.append(
            {
                "provider": provider,
                "model": model,
                "has_valid_key": has_key,
                "base_url_configured": bool(str(info.get("backend_url") or "").strip()),
            }
        )

    fallback = _fallback_configured_model()
    effective_provider = ""
    effective_model = ""
    effective_base_url = ""
    status = "missing_key"
    reason = "未检测到任何可用 Agent 模型 API Key"
    if default_provider and default_model_name and default_has_key:
        effective_provider = default_provider
        effective_model = default_model_name
        status = "configured"
        reason = "默认 Agent 模型已配置有效 API Key"
    elif fallback:
        effective_provider, effective_model, fallback_info = fallback
        status = "fallback_configured"
        reason = (
            f"默认 Agent 模型 {default_provider}/{default_model_name} 无有效 API Key，"
            f"已切换到 {effective_provider}/{effective_model}"
        )
        try:
            effective_base_url = _provider_base_url(
                effective_provider, str(fallback_info.get("backend_url") or "")
            )
        except Exception as exc:
            status = "invalid_base_url"
            reason = str(exc)

    if effective_provider and not effective_base_url:
        try:
            effective_base_url = _provider_base_url(effective_provider)
        except Exception as exc:
            status = "invalid_base_url"
            reason = str(exc)

    return {
        "status": status,
        "reason": reason,
        "default_model": default_model,
        "default_provider": default_provider,
        "default_model_name": default_model_name,
        "default_has_valid_key": default_has_key,
        "default_resolution_error": default_error,
        "effective_provider": effective_provider,
        "effective_model": effective_model,
        "effective_base_url": effective_base_url,
        "candidate_models": candidates,
        "secrets": "redacted",
    }


async def resolve_agent_model_config(principal: ResearchPrincipal) -> AgentModelConfig:
    provider_info: dict[str, Any] = {}
    default_model = _default_agent_model()
    if default_model:
        provider, model = _split_provider_model(default_model)
    else:
        provider, model, provider_info = _fallback_configured_model() or ("", "", {})
        if not provider or not model:
            raise AgentModelConfigurationError(
                "未配置可用的 Agent 模型 API Key；请在 MiniMax Token Plan、DeepSeek、Qwen 或其他启用模型中配置有效密钥"
            )
    if provider is None:
        provider_info = get_provider_and_url_by_model_sync(model)
        provider = str(provider_info.get("provider") or "").strip().lower()
    if not provider:
        raise AgentModelConfigurationError(f"未找到 Agent 模型 {model} 的提供方")
    api_key = await user_model_key_service.resolve_key_for_agent(
        user_id=principal.user_id,
        provider=provider,
        model=model,
    )
    api_key = _first_configured_text(
        api_key,
        str(provider_info.get("api_key") or ""),
        _provider_env_key(provider),
    )
    if not api_key:
        fallback = _fallback_configured_model()
        if fallback:
            provider, model, provider_info = fallback
            api_key = str(provider_info.get("api_key") or "")
    if not api_key:
        raise AgentModelConfigurationError(
            f"默认 Agent 模型 {provider}/{model} 没有有效 API Key，且未检测到 MiniMax Token Plan、DeepSeek、Qwen 等任何可用模型密钥；请确认设置页已保存到后端或系统环境变量已生效"
        )
    base_url = _provider_base_url(provider, str(provider_info.get("backend_url") or ""))
    if not base_url:
        raise AgentModelConfigurationError(f"未配置 {provider}/{model} 的 API 基础地址")
    return AgentModelConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _tool_schema(tool: ResearchTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.schema or {
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


def _provider_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message.get("role")
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
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
        provider_messages = [{"role": "system", "content": system_prompt}, *provider_messages]
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
        "input_schema": tool.schema or {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }


def _anthropic_message(message: dict[str, Any]) -> dict[str, Any] | None:
    role = message.get("role")
    content = message.get("content") or ""
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    if role == "system":
        return None
    if role == "assistant" and metadata.get("tool_calls"):
        blocks: list[dict[str, Any]] = []
        if content:
            blocks.append({"type": "text", "text": str(content)})
        for tool_call in metadata.get("tool_calls") or []:
            function = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
            raw_arguments = (
                tool_call.get("arguments")
                if "arguments" in tool_call
                else function.get("arguments")
            )
            blocks.append({
                "type": "tool_use",
                "id": str(tool_call.get("id") or tool_call.get("tool_call_id") or tool_call.get("name") or "tool_call"),
                "name": str(tool_call.get("name") or tool_call.get("tool_name") or function.get("name") or ""),
                "input": raw_arguments if isinstance(raw_arguments, dict) else _json_arguments(raw_arguments),
            })
        return {"role": "assistant", "content": blocks}
    if role == "tool":
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": str(metadata.get("tool_call_id") or metadata.get("id") or metadata.get("tool_name") or "tool_call"),
                "content": str(content),
            }],
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
            yield ModelStreamChunk(tool_call={
                "id": block.get("id"),
                "name": str(block["name"]),
                "arguments": block.get("input") if isinstance(block.get("input"), dict) else {},
            })
    yield ModelStreamChunk(finish_reason=_anthropic_finish_reason(body.get("stop_reason")))


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
                    reasoning_content = delta.get("reasoning_content") or delta.get("reasoning")
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
        current["arguments"] = f"{current.get('arguments') or ''}{function['arguments']}"


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
        tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {},
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
