from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.db.ids import DocumentId
from app.schemas.analysis import AnalysisParameters, AnalysisResult, AnalysisStatus, AnalysisTask
from app.services.analysis.service import execute as execute_module
from app.services.analysis.service.execute import AnalysisExecuteMixin


class FakeTracker:
    def __init__(self, **_kwargs: Any) -> None:
        self.messages: list[str] = []
        self.completed = False
        self.failed: str | None = None

    def update_progress(self, message: str) -> None:
        self.messages.append(message)

    def mark_completed(self) -> None:
        self.completed = True

    def mark_failed(self, message: str) -> None:
        self.failed = message


class FakeGraph:
    def propagate(self, symbol: str, analysis_date: str, progress_callback=None):
        if progress_callback is not None:
            progress_callback("执行测试分析")
        return None, {
            "summary": f"{symbol} summary",
            "recommendation": "持有",
            "confidence_score": 0.7,
            "risk_level": "中",
            "key_points": ["point"],
            "tokens_used": 120,
            "model_info": f"fake-{analysis_date}",
        }


class ExecuteOnlyService(AnalysisExecuteMixin):
    def __init__(self) -> None:
        self.status_updates: list[tuple[str, AnalysisStatus, Any]] = []
        self.usage_records: list[tuple[str, str]] = []
        self.configs: list[dict[str, Any]] = []
        self._trackers: dict[str, FakeTracker] = {}

    def _get_trading_graph(self, config: dict[str, Any]) -> FakeGraph:
        self.configs.append(config)
        return FakeGraph()

    async def _update_task_status_with_tracker(
        self,
        task_id: str,
        status: AnalysisStatus,
        tracker: FakeTracker,
        result: AnalysisResult | None = None,
    ) -> None:
        self.status_updates.append((task_id, status, result))

    async def _update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        progress: int,
        result: AnalysisResult | None = None,
    ) -> None:
        _ = progress
        self.status_updates.append((task_id, status, result))

    async def _record_token_usage(
        self,
        task: AnalysisTask,
        result: AnalysisResult,
        provider: str,
        model_name: str,
    ) -> None:
        _ = task, result
        self.usage_records.append((provider, model_name))


def _task(**parameter_overrides: Any) -> AnalysisTask:
    return AnalysisTask(
        task_id="task-1",
        user_id=DocumentId(),
        symbol="600519",
        parameters=AnalysisParameters(
            market_type="A股",
            research_depth="标准",
            selected_analysts=["market"],
            quick_analysis_model="qwen-turbo",
            deep_analysis_model="qwen-max",
            **parameter_overrides,
        ),
    )


def _patch_thread_imports(monkeypatch, created_configs: list[dict[str, Any]]) -> None:
    real_import = execute_module.importlib.import_module

    def create_analysis_config(**kwargs: Any) -> dict[str, Any]:
        created_configs.append(kwargs)
        return dict(kwargs)

    def fake_import(name: str):
        if name == "trader.utils.logging.init":
            return SimpleNamespace(
                init_logging=lambda: None,
                get_logger=lambda _name: SimpleNamespace(info=lambda *_args, **_kwargs: None),
            )
        if name == "trader.llm.clients.providers":
            return SimpleNamespace(normalize_provider_key=lambda provider: provider)
        if name == "app.services.analysis.simple":
            return SimpleNamespace(create_analysis_config=create_analysis_config)
        return real_import(name)

    monkeypatch.setattr(execute_module.importlib, "import_module", fake_import)


def test_progress_thread_execution_uses_prepared_model_context(monkeypatch):
    created_configs: list[dict[str, Any]] = []
    _patch_thread_imports(monkeypatch, created_configs)

    def fail_sync_provider(_model_name: str) -> str:
        raise AssertionError("thread execution must use prepared provider info")

    monkeypatch.setattr(
        execute_module, "get_provider_by_model_name_sync", fail_sync_provider
    )

    service = ExecuteOnlyService()
    model_context = execute_module.AnalysisThreadModelContext(
        quick_model="qwen-turbo",
        deep_model="qwen-max",
        llm_provider="qwen",
        quick_model_config={"max_tokens": 1000, "temperature": 0.2},
        deep_model_config={"max_tokens": 2000, "temperature": 0.4},
        quick_provider_info={
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "quick-key",
        },
        deep_provider_info={
            "provider": "qwen",
            "backend_url": "https://example.test/v1",
            "api_key": "deep-key",
        },
    )

    result = service._execute_analysis_sync_with_progress(
        _task(), FakeTracker(), model_context
    )

    assert result.summary == "600519 summary"
    assert created_configs[0]["quick_model_config"] == {
        "max_tokens": 1000,
        "temperature": 0.2,
    }
    assert created_configs[0]["deep_model_config"] == {
        "max_tokens": 2000,
        "temperature": 0.4,
    }
    assert created_configs[0]["quick_provider_info"]["api_key"] == "quick-key"
    assert created_configs[0]["deep_provider_info"]["api_key"] == "deep-key"


@pytest.mark.asyncio
async def test_async_execution_prefetches_model_context_before_thread(monkeypatch):
    monkeypatch.setattr(execute_module, "RedisProgressTracker", FakeTracker)

    class FakeSystemConfigs:
        async def find_one(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "llm_configs": [
                    {
                        "model_name": "qwen-turbo",
                        "max_tokens": 1000,
                        "temperature": 0.2,
                        "timeout": 30,
                        "retry_times": 1,
                        "api_base": "https://quick.example/v1",
                    },
                    {
                        "model_name": "qwen-max",
                        "max_tokens": 2000,
                        "temperature": 0.4,
                        "timeout": 60,
                        "retry_times": 2,
                        "api_base": "https://deep.example/v1",
                    },
                ]
            }

    class FakeDb:
        system_configs = FakeSystemConfigs()

    async def provider_info(model_name: str) -> dict[str, str]:
        return {
            "provider": "qwen",
            "backend_url": f"https://{model_name}.example/v1",
            "api_key": f"{model_name}-key",
        }

    monkeypatch.setattr(execute_module, "get_postgres_db", lambda: FakeDb())
    monkeypatch.setattr(execute_module, "get_provider_and_url_by_model", provider_info)

    service = ExecuteOnlyService()
    captured_contexts: list[Any] = []

    def execute_in_thread(
        task: AnalysisTask,
        tracker: FakeTracker,
        model_context: Any,
    ) -> AnalysisResult:
        _ = task, tracker
        captured_contexts.append(model_context)
        return AnalysisResult(
            analysis_id="analysis-1",
            summary="done",
            recommendation="持有",
            tokens_used=10,
        )

    monkeypatch.setattr(
        service, "_execute_analysis_sync_with_progress", execute_in_thread
    )

    await service._execute_single_analysis_async(_task())

    assert captured_contexts
    assert captured_contexts[0].quick_model_config["max_tokens"] == 1000
    assert captured_contexts[0].deep_model_config["timeout"] == 60
    assert captured_contexts[0].quick_provider_info["api_key"] == "qwen-turbo-key"
    assert service.usage_records == [("qwen", "qwen-max")]
    assert service.status_updates[-1][1] == AnalysisStatus.COMPLETED
