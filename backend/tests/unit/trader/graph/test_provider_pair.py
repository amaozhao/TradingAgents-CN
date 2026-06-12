from trader.graph.trading import _create_provider_pair, create_llm_by_provider
from trader.graph.trading import TradingAgentsGraph


def test_create_minimax_token_plan_provider_pair_uses_saved_keys():
    config = {
        "quick_think_llm": "MiniMax-M2",
        "deep_think_llm": "MiniMax-M2",
        "backend_url": "https://api.minimaxi.com/anthropic",
        "quick_api_key": "test-quick-key",
        "deep_api_key": "test-deep-key",
    }

    deep_llm, quick_llm = _create_provider_pair(
        provider="minimax-token-plan",
        config=config,
        quick_temperature=0.1,
        quick_max_tokens=512,
        quick_timeout=30,
        deep_temperature=0.2,
        deep_max_tokens=1024,
        deep_timeout=60,
    )

    assert quick_llm.model == "MiniMax-M2"
    assert deep_llm.model == "MiniMax-M2"
    assert str(quick_llm._client.api_key) == "test-quick-key"
    assert str(deep_llm._client.api_key) == "test-deep-key"
    assert quick_llm.max_tokens == 512
    assert deep_llm.max_tokens == 1024


def test_create_llm_by_provider_keeps_openai_compatible_base_url():
    llm = create_llm_by_provider(
        provider="qwen",
        model="qwen-turbo",
        backend_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-qwen-key",
        temperature=0.3,
        max_tokens=256,
        timeout=45,
    )

    assert llm.model_name == "qwen-turbo"
    assert llm.openai_api_key.get_secret_value() == "test-qwen-key"
    assert str(llm.openai_api_base).rstrip("/") == (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_minimax_token_plan_model_api_base_uses_provider_anthropic_url(monkeypatch):
    from app.core import database
    from app.services.analysis.simple.provider import get_provider_and_url_by_model_sync

    class Collection:
        def __init__(self, docs):
            self.docs = docs

        def find_one(self, query, sort=None):
            for doc in self.docs:
                if all(doc.get(key) == value for key, value in query.items()):
                    return doc
            return None

    class Db:
        system_configs = Collection(
            [
                {
                    "is_active": True,
                    "version": 1,
                    "llm_configs": [
                        {
                            "provider": "minimax-token-plan",
                            "model_name": "MiniMax-M3",
                            "api_base": "https://platform.minimaxi.com",
                            "api_key": "",
                        }
                    ],
                }
            ]
        )
        llm_providers = Collection(
            [
                {
                    "name": "minimax-token-plan",
                    "api_key": "test-provider-key",
                    "default_base_url": "https://api.minimaxi.com/anthropic",
                }
            ]
        )

    monkeypatch.setattr(database, "get_postgres_db_sync", lambda: Db())

    provider_info = get_provider_and_url_by_model_sync("MiniMax-M3")

    assert provider_info["provider"] == "minimax-token-plan"
    assert provider_info["api_key"] == "test-provider-key"
    assert provider_info["backend_url"] == "https://api.minimaxi.com/anthropic"


def test_values_stream_state_replaces_final_state_without_node_merge():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.debug = False
    graph.config = {"checkpoint_enabled": False, "data_cache_dir": "/tmp"}
    graph._checkpointer_ctx = None
    graph.deep_thinking_llm = object()
    graph._resolve_pending_entries = lambda *_args, **_kwargs: None
    graph.resolve_instrument_context = lambda *_args, **_kwargs: ""
    graph._print_timing_summary = lambda *_args, **_kwargs: None
    graph._log_state = lambda *_args, **_kwargs: None
    graph.process_signal = lambda decision, _company: {"decision": decision}

    class MemoryLog:
        def get_past_context(self, _company):
            return ""

        def store_decision(self, **_kwargs):
            return None

    class Propagator:
        def create_initial_state(self, *_args, **_kwargs):
            return {"messages": [], "final_trade_decision": "持有"}

        def get_graph_args(self, **_kwargs):
            return {"stream_mode": "values"}

    class StreamGraph:
        def stream(self, _state, **_kwargs):
            yield {
                "messages": [],
                "final_trade_decision": "持有",
                "company_of_interest": "600519",
            }

    graph.memory_log = MemoryLog()
    graph.propagator = Propagator()
    graph.graph = StreamGraph()

    final_state, decision = graph.propagate("600519", "2026-06-06")

    assert final_state["final_trade_decision"] == "持有"
    assert decision["decision"] == "持有"
