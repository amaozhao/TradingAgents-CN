from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.schemas.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.analysis.simple import base as base_module
from app.services.analysis.simple import task as task_module
from app.services.analysis.simple.base import BaseAnalysisMixin
from app.services.analysis.simple.task import AnalysisTaskMixin
from app.services.analysis.simple import runner as runner_module
from app.services.analysis.simple.runner import AnalysisRunnerMixin


class FakeTracker:
    def __init__(self) -> None:
        self.progress_data = {"progress_percentage": 0}
        self.updates: list[Any] = []

    def update_progress(self, update: Any) -> None:
        self.updates.append(update)
        if isinstance(update, dict) and "progress_percentage" in update:
            self.progress_data["progress_percentage"] = update["progress_percentage"]


class FakeMemoryManager:
    async def create_task(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(task_id=kwargs["task_id"])

    async def get_task(self, task_id: str) -> SimpleNamespace:
        return SimpleNamespace(task_id=task_id)

    async def update_task_status(self, **_kwargs: Any) -> None:
        return None


class FakeGraph:
    config = {"quick_think_llm": "qwen-turbo", "deep_think_llm": "qwen-max"}

    def propagate(
        self,
        _symbol: str,
        _analysis_date: str,
        progress_callback=None,
        **_kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if progress_callback is not None:
            progress_callback("📊 市场分析师")
        return {}, {
            "summary": "summary",
            "recommendation": "持有",
            "confidence_score": 0.7,
            "risk_level": "中",
            "key_points": ["point"],
        }


class RunnerOnlyService(AnalysisRunnerMixin):
    def __init__(self) -> None:
        self.memory_manager = FakeMemoryManager()

    def _get_trading_graph(self, _config: dict[str, Any]) -> FakeGraph:
        return FakeGraph()


class BaseOnlyService(BaseAnalysisMixin):
    pass


class TaskOnlyService(AnalysisTaskMixin):
    def __init__(self) -> None:
        self.memory_manager = FakeMemoryManager()
        self._thread_pool = None
        self.prepared_context = object()
        self.captured_contexts: list[Any] = []

    async def _prepare_analysis_thread_context(
        self, _request: SingleAnalysisRequest
    ) -> object:
        return self.prepared_context

    def _run_analysis_sync(
        self,
        _task_id: str,
        _user_id: str,
        _request: SingleAnalysisRequest,
        _tracker: Any,
        _runtime_loop: Any,
        model_context: Any = None,
    ) -> dict[str, Any]:
        self.captured_contexts.append(model_context)
        return {"status": "completed"}

    async def _resolve_stock_name_async(self, _code: str) -> str:
        return "贵州茅台"

    def _resolve_stock_name(self, _code: str) -> str:
        raise AssertionError(
            "async task creation must not call sync stock-name resolver"
        )


def test_runner_progress_updates_do_not_use_sync_database(monkeypatch):
    sync_db_calls: list[None] = []
    real_import_module = runner_module.importlib.import_module

    def fake_import_module(name: str):
        if name == "trader.utils.logging.init":
            return SimpleNamespace(
                init_logging=lambda: None,
                get_logger=lambda _name: SimpleNamespace(
                    info=lambda *_args, **_kwargs: None
                ),
            )
        if name == "app.services.capability":
            return SimpleNamespace(
                get_model_capability_service=lambda: SimpleNamespace(
                    validate_model_pair=lambda *_args, **_kwargs: {
                        "valid": True,
                        "warnings": [],
                    },
                    recommend_models_for_depth=lambda _depth: (
                        "qwen-turbo",
                        "qwen-max",
                    ),
                )
            )
        if name == "trader.utils.flows":
            return SimpleNamespace(
                get_trading_date_range=lambda analysis_date, **_kwargs: (
                    analysis_date,
                    analysis_date,
                )
            )
        if name == "threading":
            return SimpleNamespace(
                Thread=lambda **_kwargs: SimpleNamespace(start=lambda: None)
            )
        if name == "app.core.database":
            return SimpleNamespace(
                get_postgres_db_sync=lambda: sync_db_calls.append(None)
            )
        return real_import_module(name)

    monkeypatch.setattr(runner_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        runner_module,
        "get_provider_and_url_by_model_sync",
        lambda model: {
            "provider": "qwen",
            "backend_url": f"https://{model}.example/v1",
            "api_key": f"{model}-key",
        },
    )
    monkeypatch.setattr(
        runner_module,
        "create_analysis_config",
        lambda **kwargs: dict(kwargs),
    )
    service = RunnerOnlyService()
    request = SingleAnalysisRequest(
        symbol="600519",
        parameters=AnalysisParameters(
            analysis_date="2026-06-15",
            selected_analysts=["market"],
            quick_analysis_model="qwen-turbo",
            deep_analysis_model="qwen-max",
        ),
    )

    service._run_analysis_sync("task-1", "user-1", request, FakeTracker())

    assert sync_db_calls == []


def test_analysis_thread_pool_uses_configured_worker_limit(monkeypatch):
    captured_limits: list[int] = []
    real_import_module = base_module.importlib.import_module

    class FakeThreadPoolExecutor:
        def __init__(self, max_workers: int) -> None:
            captured_limits.append(max_workers)

    def fake_import_module(name: str):
        if name == "concurrent":
            return SimpleNamespace(
                futures=SimpleNamespace(ThreadPoolExecutor=FakeThreadPoolExecutor)
            )
        if name == "app.services.socket":
            return SimpleNamespace(get_websocket_manager=lambda: SimpleNamespace())
        return real_import_module(name)

    monkeypatch.setattr(base_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(base_module.settings, "ANALYSIS_MAX_WORKERS", 5, raising=False)

    BaseOnlyService()

    assert captured_limits == [5]


def test_runner_thread_uses_prepared_model_context_without_sync_provider(monkeypatch):
    from app.services.analysis.simple.runner import SimpleAnalysisThreadContext

    real_import_module = runner_module.importlib.import_module

    def fake_import_module(name: str):
        if name == "trader.utils.logging.init":
            return SimpleNamespace(
                init_logging=lambda: None,
                get_logger=lambda _name: SimpleNamespace(
                    info=lambda *_args, **_kwargs: None
                ),
            )
        if name == "app.services.capability":
            return SimpleNamespace(
                get_model_capability_service=lambda: SimpleNamespace(
                    validate_model_pair=lambda *_args, **_kwargs: {
                        "valid": True,
                        "warnings": [],
                    },
                    recommend_models_for_depth=lambda _depth: (
                        "qwen-turbo",
                        "qwen-max",
                    ),
                )
            )
        if name == "trader.utils.flows":
            return SimpleNamespace(
                get_trading_date_range=lambda analysis_date, **_kwargs: (
                    analysis_date,
                    analysis_date,
                )
            )
        if name == "threading":
            return SimpleNamespace(
                Thread=lambda **_kwargs: SimpleNamespace(start=lambda: None)
            )
        return real_import_module(name)

    monkeypatch.setattr(runner_module.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        runner_module,
        "get_provider_and_url_by_model_sync",
        lambda _model: (_ for _ in ()).throw(
            AssertionError("thread runner must use prepared provider info")
        ),
    )
    created_configs: list[dict[str, Any]] = []

    def create_config(**kwargs: Any) -> dict[str, Any]:
        created_configs.append(kwargs)
        return dict(kwargs)

    monkeypatch.setattr(runner_module, "create_analysis_config", create_config)

    service = RunnerOnlyService()
    request = SingleAnalysisRequest(
        symbol="600519",
        parameters=AnalysisParameters(
            analysis_date="2026-06-15",
            selected_analysts=["market"],
            quick_analysis_model="qwen-turbo",
            deep_analysis_model="qwen-max",
        ),
    )
    context = SimpleAnalysisThreadContext(
        quick_model="qwen-turbo",
        deep_model="qwen-max",
        llm_provider="qwen",
        quick_provider_info={
            "provider": "qwen",
            "backend_url": "https://quick.example/v1",
            "api_key": "quick-key",
        },
        deep_provider_info={
            "provider": "qwen",
            "backend_url": "https://deep.example/v1",
            "api_key": "deep-key",
        },
    )

    service._run_analysis_sync(
        "task-1", "user-1", request, FakeTracker(), None, context
    )

    assert created_configs[0]["quick_provider_info"]["api_key"] == "quick-key"
    assert created_configs[0]["deep_provider_info"]["api_key"] == "deep-key"


@pytest.mark.asyncio
async def test_submit_to_thread_pool_prefetches_model_context() -> None:
    service = TaskOnlyService()
    request = SingleAnalysisRequest(
        symbol="600519",
        parameters=AnalysisParameters(
            selected_analysts=["market"],
            quick_analysis_model="qwen-turbo",
            deep_analysis_model="qwen-max",
        ),
    )

    await service._execute_analysis_sync("task-1", "user-1", request, FakeTracker())

    assert service.captured_contexts == [service.prepared_context]


@pytest.mark.asyncio
async def test_create_analysis_task_uses_async_stock_name_resolver(monkeypatch) -> None:
    class FakeTasksCollection:
        async def update_one(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(upserted_id="task-1", matched_count=0)

    class FakeDb:
        analysis_tasks = FakeTasksCollection()

    async def dual_write(_collection: str, _document: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(task_module, "get_postgres_db", lambda: FakeDb())
    monkeypatch.setattr(task_module, "dual_write_hot_document", dual_write)

    service = TaskOnlyService()
    request = SingleAnalysisRequest(
        symbol="600519",
        parameters=AnalysisParameters(selected_analysts=["market"]),
    )

    await service.create_analysis_task("user-1", request)
