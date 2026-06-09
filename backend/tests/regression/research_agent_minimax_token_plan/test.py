import pytest

from app.services.research_agent import provider_client as pc
from app.services.research_agent.loop import ResearchTool


def test_minimax_token_plan_base_url_matches_source_contract():
    assert (
        pc._provider_base_url("minimax-token-plan", "")
        == "https://api.minimaxi.com/anthropic"
    )
    assert (
        pc._provider_base_url(
            "minimax-token-plan", "https://api.minimax.io/anthropic"
        )
        == "https://api.minimax.io/anthropic"
    )

    with pytest.raises(pc.AgentModelConfigurationError):
        pc._provider_base_url("minimax-token-plan", "http://api.minimaxi.com/anthropic")
    with pytest.raises(pc.AgentModelConfigurationError):
        pc._provider_base_url("minimax-token-plan", "https://example.com/anthropic")
    with pytest.raises(pc.AgentModelConfigurationError):
        pc._provider_base_url("minimax-token-plan", "https://api.minimaxi.com/v1")


def test_minimax_token_plan_headers_match_source_contract():
    headers = pc._anthropic_headers("test-minimax-key-1234567890")

    assert headers["Authorization"] == "Bearer test-minimax-key-1234567890"
    assert headers["x-api-key"] == "test-minimax-key-1234567890"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "tradingagents-cn (python)"


def test_minimax_token_plan_message_conversion_matches_anthropic_shape():
    messages = pc._anthropic_messages(
        [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "find AAPL"},
            {
                "role": "assistant",
                "content": "I will call a tool",
                "metadata": {
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "lookup_symbol",
                                "arguments": '{"symbol":"AAPL"}',
                            },
                        }
                    ]
                },
            },
            {
                "role": "tool",
                "content": '{"price": 123}',
                "metadata": {"tool_call_id": "call_1"},
            },
        ]
    )

    assert messages == [
        {"role": "user", "content": "find AAPL"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I will call a tool"},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "lookup_symbol",
                    "input": {"symbol": "AAPL"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": '{"price": 123}',
                }
            ],
        },
    ]


@pytest.mark.asyncio
async def test_minimax_token_plan_request_and_response(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": [
                    {"type": "thinking", "thinking": "reasoning"},
                    {"type": "text", "text": "OK"},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "lookup_symbol",
                        "input": {"symbol": "AAPL"},
                    },
                ],
                "stop_reason": "tool_use",
            }

    class _FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(pc.httpx, "AsyncClient", _FakeAsyncClient)

    chunks = [
        chunk
        async for chunk in pc._complete_anthropic_message(
            config=pc.AgentModelConfig(
                provider="minimax-token-plan",
                model="MiniMax-M3",
                api_key="test-minimax-key-1234567890",
                base_url="https://api.minimaxi.com/anthropic",
                timeout_seconds=12,
            ),
            system_prompt="system prompt",
            messages=[{"role": "user", "content": "reply OK"}],
            tools=[
                ResearchTool(
                    name="lookup_symbol",
                    description="Look up a symbol",
                    permission="agent:use",
                    schema={
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                    handler=lambda **_kwargs: {},
                )
            ],
        )
    ]

    assert captured["timeout"] == 12
    assert captured["url"] == "https://api.minimaxi.com/anthropic/v1/messages"
    assert captured["headers"]["Authorization"] == "Bearer test-minimax-key-1234567890"
    assert captured["headers"]["x-api-key"] == "test-minimax-key-1234567890"
    assert captured["json"] == {
        "model": "MiniMax-M3",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": "reply OK"}],
        "system": "system prompt",
        "tools": [
            {
                "name": "lookup_symbol",
                "description": "Look up a symbol",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        ],
    }
    assert [chunk.reasoning_content for chunk in chunks if chunk.reasoning_content] == [
        "reasoning"
    ]
    assert [chunk.delta for chunk in chunks if chunk.delta] == ["OK"]
    assert [chunk.tool_call for chunk in chunks if chunk.tool_call] == [
        {"id": "toolu_1", "name": "lookup_symbol", "arguments": {"symbol": "AAPL"}}
    ]
    assert chunks[-1].finish_reason == "tool_calls"


def test_configured_candidate_models_deduplicates_minimax_provider(monkeypatch):
    class _FakeCursor(list):
        pass

    class _FakeCollection:
        def __init__(self, docs):
            self.docs = docs

        def find_one(self, *_args, **_kwargs):
            return self.docs[0] if self.docs else None

        def find(self, *_args, **_kwargs):
            return _FakeCursor(self.docs)

    class _FakeDb:
        system_configs = _FakeCollection(
            [
                {
                    "is_active": True,
                    "llm_configs": [
                        {
                            "enabled": True,
                            "provider": "minimax-token-plan",
                            "model_name": "MiniMax-M3",
                            "api_key": "",
                            "api_base": "",
                        }
                    ],
                }
            ]
        )
        llm_providers = _FakeCollection(
            [
                {
                    "name": "minimax-token-plan",
                    "api_key": "test-minimax-key-1234567890",
                    "default_base_url": "https://api.minimaxi.com/anthropic",
                }
            ]
        )

    monkeypatch.setattr(pc, "get_postgres_db_sync", lambda: _FakeDb())

    candidates = pc._configured_candidate_models()

    assert [
        (provider, model)
        for provider, model, _info in candidates
        if provider == "minimax-token-plan"
    ] == [("minimax-token-plan", "MiniMax-M3")]
