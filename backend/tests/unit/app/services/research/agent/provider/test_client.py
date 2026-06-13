from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.research.agent.provider import client as provider_module
from app.services.research.agent.context import ResearchPrincipal
from app.services.research.agent.provider.client import (
    AgentModelConfigurationError,
    OpenAICompatibleModelClient,
)
from app.services.research.agent.registry import ResearchTool


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "先读取数据。",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "market_data_lookup",
                                    "arguments": '{"symbol":"600519"}',
                                },
                            }
                        ],
                    },
                }
            ]
        }


class FakeAsyncClient:
    last_payload: dict[str, Any] | None = None
    last_url: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        FakeAsyncClient.last_url = url
        FakeAsyncClient.last_payload = kwargs["json"]
        return FakeResponse()


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeStreamContext:
    def __init__(self, response: FakeStreamResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeStreamResponse:
        return self.response

    async def __aexit__(self, *_args: Any) -> None:
        return None


class FakeStreamingAsyncClient(FakeAsyncClient):
    stream_payload: dict[str, Any] | None = None

    def stream(self, _method: str, url: str, **kwargs: Any) -> FakeStreamContext:
        FakeAsyncClient.last_url = url
        FakeStreamingAsyncClient.stream_payload = kwargs["json"]
        return FakeStreamContext(
            FakeStreamResponse(
                [
                    "data: "
                    + json.dumps(
                        {
                            "choices": [
                                {"delta": {"content": "先"}, "finish_reason": None}
                            ]
                        }
                    ),
                    "data: "
                    + json.dumps(
                        {
                            "choices": [
                                {
                                    "delta": {
                                        "content": "读",
                                        "reasoning_content": "需要先查行情",
                                    },
                                    "finish_reason": None,
                                }
                            ]
                        }
                    ),
                    "data: "
                    + json.dumps(
                        {
                            "choices": [
                                {
                                    "delta": {
                                        "tool_calls": [
                                            {
                                                "index": 0,
                                                "id": "call-1",
                                                "type": "function",
                                                "thought_signature": "sig-1",
                                                "function": {
                                                    "name": "market_data_lookup",
                                                    "arguments": '{"sym',
                                                },
                                            }
                                        ]
                                    },
                                    "finish_reason": None,
                                }
                            ]
                        }
                    ),
                    "data: "
                    + json.dumps(
                        {
                            "choices": [
                                {
                                    "delta": {
                                        "tool_calls": [
                                            {
                                                "index": 0,
                                                "function": {
                                                    "arguments": 'bol":"600519"}',
                                                },
                                            }
                                        ]
                                    },
                                    "finish_reason": "tool_calls",
                                }
                            ]
                        }
                    ),
                    "data: [DONE]",
                ]
            )
        )


class FakeFallbackAsyncClient(FakeAsyncClient):
    def stream(self, *_args: Any, **_kwargs: Any) -> FakeStreamContext:
        raise RuntimeError("stream unavailable")


def _principal() -> ResearchPrincipal:
    return ResearchPrincipal.from_user(USER_A)


@pytest.mark.asyncio
async def test_missing_default_model_fails_visibly(monkeypatch):
    monkeypatch.setattr(
        provider_module._provider_resolver, "default_agent_model", lambda: ""
    )
    monkeypatch.setattr(
        provider_module._provider_resolver, "fallback_configured_model", lambda: None
    )

    with pytest.raises(
        AgentModelConfigurationError, match="未配置可用的 Agent 模型 API Key"
    ):
        await provider_module.resolve_agent_model_config(_principal())


@pytest.mark.asyncio
async def test_openai_compatible_client_maps_tool_calls(monkeypatch):
    async def no_user_key(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        provider_module.user_model_key_service,
        "resolve_key_for_agent",
        no_user_key,
    )
    monkeypatch.setattr(
        provider_module.settings, "TRADING_AGENTS_DEFAULT_MODEL", "openai/gpt-test"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_API_KEY", "sk-test-valid-123456"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_BASE_URL", "https://example.test/v1"
    )
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", FakeAsyncClient)

    chunks = [
        chunk
        async for chunk in OpenAICompatibleModelClient(_principal()).stream(
            messages=[{"role": "user", "content": "查 600519"}],
            tools=[
                ResearchTool(
                    name="market_data_lookup",
                    description="Lookup market data.",
                    permission="research.market.data.read",
                    schema={
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                )
            ],
        )
    ]

    assert FakeAsyncClient.last_url == "https://example.test/v1/chat/completions"
    assert FakeAsyncClient.last_payload["model"] == "gpt-test"
    assert FakeAsyncClient.last_payload["messages"] == [
        {"role": "user", "content": "查 600519"}
    ]
    assert (
        FakeAsyncClient.last_payload["tools"][0]["function"]["name"]
        == "market_data_lookup"
    )
    assert chunks[0].delta == "先读取数据。"
    assert chunks[1].tool_call == {
        "id": "call-1",
        "name": "market_data_lookup",
        "arguments": {"symbol": "600519"},
    }
    assert chunks[2].finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_openai_compatible_client_streams_sse_chunks(monkeypatch):
    async def no_user_key(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        provider_module.user_model_key_service,
        "resolve_key_for_agent",
        no_user_key,
    )
    monkeypatch.setattr(
        provider_module.settings, "TRADING_AGENTS_DEFAULT_MODEL", "openai/gpt-test"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_API_KEY", "sk-test-valid-123456"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_BASE_URL", "https://example.test/v1"
    )
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", FakeStreamingAsyncClient)

    chunks = [
        chunk
        async for chunk in OpenAICompatibleModelClient(_principal()).stream(
            messages=[{"role": "user", "content": "查 600519"}],
            tools=[
                ResearchTool(
                    name="market_data_lookup",
                    description="Lookup market data.",
                    permission="research.market.data.read",
                    schema={"type": "object", "properties": {}},
                )
            ],
        )
    ]

    assert FakeStreamingAsyncClient.stream_payload["stream"] is True
    assert chunks[0].delta == "先"
    assert chunks[1].delta == "读"
    assert chunks[2].reasoning_content == "需要先查行情"
    assert chunks[3].tool_call == {
        "id": "call-1",
        "name": "market_data_lookup",
        "arguments": {"symbol": "600519"},
        "thought_signature": "sig-1",
    }
    assert chunks[4].finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_streaming_failure_before_output_falls_back_to_complete(monkeypatch):
    async def no_user_key(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        provider_module.user_model_key_service,
        "resolve_key_for_agent",
        no_user_key,
    )
    monkeypatch.setattr(
        provider_module.settings, "TRADING_AGENTS_DEFAULT_MODEL", "openai/gpt-test"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_API_KEY", "sk-test-valid-123456"
    )
    monkeypatch.setattr(
        provider_module.settings, "OPENAI_BASE_URL", "https://example.test/v1"
    )
    monkeypatch.setattr(provider_module.httpx, "AsyncClient", FakeFallbackAsyncClient)

    chunks = [
        chunk
        async for chunk in OpenAICompatibleModelClient(_principal()).stream(
            messages=[{"role": "user", "content": "查 600519"}],
            tools=[],
        )
    ]

    assert chunks[0].delta == "先读取数据。"
