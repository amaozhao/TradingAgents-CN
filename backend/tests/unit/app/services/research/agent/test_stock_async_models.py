from __future__ import annotations

from typing import Any

import pytest

from app.services.research.agent import stock


def _active_config_doc() -> dict[str, Any]:
    return {
        "default_llm": "qwen-fallback",
        "system_settings": {
            "quick_analysis_model": "qwen-turbo",
            "deep_analysis_model": "qwen-plus",
        },
        "llm_configs": [
            {
                "model_name": "qwen-turbo",
                "provider": "qwen",
                "enabled": True,
                "suitable_roles": ["quick_analysis"],
                "priority": 10,
                "capability_level": 2,
                "performance_metrics": {"speed": 9},
                "input_price_per_1k": 0.01,
                "output_price_per_1k": 0.02,
                "currency": "CNY",
            },
            {
                "model_name": "qwen-plus",
                "provider": "qwen",
                "enabled": True,
                "suitable_roles": ["deep_analysis"],
                "priority": 10,
                "capability_level": 4,
                "performance_metrics": {"quality": 9},
                "input_price_per_1k": 0.02,
                "output_price_per_1k": 0.04,
                "currency": "CNY",
            },
        ],
    }


@pytest.mark.asyncio
async def test_analysis_parameters_use_async_model_resolution(monkeypatch):
    async def async_config_doc() -> dict[str, Any]:
        return _active_config_doc()

    async def async_provider_info(model_name: str) -> dict[str, str]:
        return {
            "provider": "qwen",
            "backend_url": "https://dashscope.example/v1",
            "api_key": f"{model_name}-valid-key",
        }

    def sync_config_doc() -> dict[str, Any]:
        raise AssertionError("async stock analysis must not load config via sync DB")

    def sync_provider_info(_model_name: str) -> dict[str, str]:
        raise AssertionError("async stock analysis must not call sync provider resolver")

    monkeypatch.setattr(stock, "_load_active_system_config_doc_async", async_config_doc)
    monkeypatch.setattr(stock, "_load_active_system_config_doc", sync_config_doc)
    monkeypatch.setattr(stock, "get_provider_and_url_by_model", async_provider_info)
    monkeypatch.setattr(stock, "get_provider_and_url_by_model_sync", sync_provider_info)

    parameters, skipped_stages, stage_plan = await stock._analysis_parameters_async(
        {"market_type": "A股", "selected_analysts": ["market", "fundamentals"]}
    )
    missing_keys = await stock._missing_model_keys_async(parameters)

    assert parameters.quick_analysis_model == "qwen-turbo"
    assert parameters.deep_analysis_model == "qwen-plus"
    assert {stage["stage"] for stage in skipped_stages} == {
        "news_analysis",
        "social_analysis",
    }
    assert stage_plan
    assert missing_keys == []


@pytest.mark.asyncio
async def test_usage_record_uses_async_provider_and_pricing(monkeypatch):
    calls: list[str] = []

    async def async_provider_info(model_name: str) -> dict[str, str]:
        calls.append(model_name)
        return {
            "provider": "qwen",
            "backend_url": "https://dashscope.example/v1",
            "api_key": "configured-key",
        }

    async def async_config_doc() -> dict[str, Any]:
        return _active_config_doc()

    def sync_provider_info(_model_name: str) -> dict[str, str]:
        raise AssertionError("usage recording must not call sync provider resolver")

    def sync_config_doc() -> dict[str, Any]:
        raise AssertionError("usage pricing must not load config via sync DB")

    async def add_usage_record(record: Any) -> None:
        assert record.provider == "qwen"
        assert record.model_name == "qwen-plus"
        assert record.currency == "CNY"

    monkeypatch.setattr(stock, "get_provider_and_url_by_model", async_provider_info)
    monkeypatch.setattr(stock, "get_provider_and_url_by_model_sync", sync_provider_info)
    monkeypatch.setattr(stock, "_load_active_system_config_doc_async", async_config_doc)
    monkeypatch.setattr(stock, "_load_active_system_config_doc", sync_config_doc)
    monkeypatch.setattr(
        stock.usage_statistics_service, "add_usage_record", add_usage_record
    )

    await stock._record_stock_workflow_usage(
        task_id="task-1",
        symbol="600519",
        parameters=stock.AnalysisParameters(
            market_type="A股",
            research_depth="标准",
            selected_analysts=["market"],
            quick_analysis_model="qwen-turbo",
            deep_analysis_model="qwen-plus",
        ),
        report={"summary": "ok", "recommendation": "hold", "tokens_used": 100},
    )

    assert calls == ["qwen-plus"]
