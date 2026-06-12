from app.services.analysis.simple.provider import create_analysis_config


def test_web_analysis_config_enables_langgraph_checkpointing(monkeypatch):
    monkeypatch.setattr(
        "app.services.analysis.simple.provider.get_provider_and_url_by_model_sync",
        lambda _model: {
            "provider": "minimax-token-plan",
            "backend_url": "https://api.minimaxi.com/anthropic",
            "api_key": "test-key",
        },
    )

    config = create_analysis_config(
        research_depth="3",
        selected_analysts=["market", "fundamentals"],
        quick_model="MiniMax-M3",
        deep_model="MiniMax-M3",
        llm_provider="minimax-token-plan",
    )

    assert config["checkpoint_enabled"] is True
