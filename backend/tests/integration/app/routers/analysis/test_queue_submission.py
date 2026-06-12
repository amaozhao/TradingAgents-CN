from __future__ import annotations

import inspect

import pytest

from app.worker import analysis as analysis_worker
from app.routers import analysis
from app.schemas.analysis import (
    AnalysisParameters,
    BatchAnalysisRequest,
    SingleAnalysisRequest,
)


class _SimpleService:
    def __init__(self) -> None:
        self.created_requests: list[SingleAnalysisRequest] = []

    async def create_analysis_task(self, user_id: str, request: SingleAnalysisRequest):
        self.created_requests.append(request)
        task_no = len(self.created_requests)
        symbol = request.get_symbol()
        return {
            "task_id": f"task-{task_no}",
            "symbol": symbol,
            "stock_code": symbol,
            "status": "pending",
            "message": "任务已创建，等待执行",
        }

    async def execute_analysis_background(self, *args, **kwargs):
        raise AssertionError("analysis must not run inside the FastAPI process")


class _QueueService:
    def __init__(self) -> None:
        self.enqueued: list[dict] = []

    async def enqueue_task(
        self,
        user_id: str,
        symbol: str,
        params: dict,
        batch_id: str | None = None,
        task_id: str | None = None,
    ) -> str:
        self.enqueued.append(
            {
                "user_id": user_id,
                "symbol": symbol,
                "params": params,
                "batch_id": batch_id,
                "task_id": task_id,
            }
        )
        return task_id or f"queued-{len(self.enqueued)}"


@pytest.fixture
def queue_submission_fakes(monkeypatch):
    simple_service = _SimpleService()
    queue_service = _QueueService()

    monkeypatch.setattr(analysis, "get_simple_analysis_service", lambda: simple_service)
    monkeypatch.setattr(analysis, "get_queue_service", lambda: queue_service)

    def fail_in_process_task_creation(coro):
        if inspect.iscoroutine(coro):
            coro.close()
        raise AssertionError("route must enqueue work instead of create_task")

    monkeypatch.setattr(analysis.asyncio, "create_task", fail_in_process_task_creation)
    return simple_service, queue_service


@pytest.mark.asyncio
async def test_single_analysis_submission_only_enqueues_work(queue_submission_fakes):
    _, queue_service = queue_submission_fakes

    result = await analysis.submit_single_analysis(
        SingleAnalysisRequest(
            symbol="600519",
            parameters=AnalysisParameters(
                quick_analysis_model=None,
                deep_analysis_model=None,
            ),
        ),
        None,
        {"id": "user-1"},
    )

    assert result["success"] is True
    assert result["data"]["task_id"] == "task-1"
    assert queue_service.enqueued == [
        {
            "user_id": "user-1",
            "symbol": "600519",
            "params": {
                "market_type": "A股",
                "analysis_date": None,
                "research_depth": "标准",
                "selected_analysts": ["market", "fundamentals", "news", "social"],
                "custom_prompt": None,
                "include_sentiment": True,
                "include_risk": True,
                "language": "zh-CN",
                "quick_analysis_model": None,
                "deep_analysis_model": None,
                "task_id": "task-1",
                "stock_code": "600519",
                "symbol": "600519",
                "user_id": "user-1",
            },
            "batch_id": None,
            "task_id": "task-1",
        }
    ]


@pytest.mark.asyncio
async def test_batch_analysis_submission_uses_workflow_submit_adapter(
    monkeypatch,
    queue_submission_fakes,
):
    _, queue_service = queue_submission_fakes
    calls: list[dict] = []

    class FakeBatchWorkflow:
        def __init__(self, *, tool_name: str) -> None:
            assert tool_name == "batch_stock_analysis"

        async def submit(self, _context, payload: dict):
            calls.append(payload)
            return {
                "batch_id": "batch-1",
                "task_ids": ["task-1", "task-2"],
                "mapping": [
                    {"symbol": "600519", "stock_code": "600519", "task_id": "task-1"},
                    {"symbol": "000001", "stock_code": "000001", "task_id": "task-2"},
                ],
                "status": "processing",
            }

    monkeypatch.setattr(analysis, "BatchStockWorkflow", FakeBatchWorkflow)

    result = await analysis.submit_batch_analysis(
        BatchAnalysisRequest(
            title="batch",
            symbols=["600519", "000001"],
            parameters=AnalysisParameters(
                quick_analysis_model=None,
                deep_analysis_model=None,
            ),
        ),
        {"id": "user-1"},
    )

    assert result["success"] is True
    assert result["data"]["task_ids"] == ["task-1", "task-2"]
    assert result["data"]["batch_id"] == "batch-1"
    assert result["data"]["mapping"][0]["symbol"] == "600519"
    assert result["data"]["status"] == "processing"
    assert calls == [
        {
            "title": "batch",
            "symbols": ["600519", "000001"],
            "parameters": {
                "market_type": "A股",
                "research_depth": "标准",
                "selected_analysts": ["market", "fundamentals", "news", "social"],
                "include_sentiment": True,
                "include_risk": True,
                "language": "zh-CN",
            },
            "wait_for_completion": False,
        }
    ]
    assert queue_service.enqueued == []


class _WorkerQueueService:
    def __init__(self) -> None:
        self.acked: list[tuple[str, bool]] = []

    async def ack_task(self, task_id: str, success: bool):
        self.acked.append((task_id, success))


class _WorkerSimpleService:
    _DEFAULT_STATUS = {"task_id": "task-1", "status": "completed"}

    def __init__(self, status: dict | None = _DEFAULT_STATUS) -> None:
        self.calls: list[dict] = []
        self.status = status
        self.status_updates: list[tuple[str, object, int]] = []

    async def execute_analysis_background(self, task_id, user_id, request):
        self.calls.append(
            {
                "task_id": task_id,
                "user_id": user_id,
                "symbol": request.get_symbol(),
                "market_type": request.parameters.market_type,
            }
        )

    async def get_task_status(self, task_id):
        return self.status

    async def _update_task_status(self, task_id, status, progress):
        self.status_updates.append((task_id, status, progress))


@pytest.mark.asyncio
async def test_worker_processes_queued_task_with_simple_analysis_service(monkeypatch):
    simple_service = _WorkerSimpleService()
    queue_service = _WorkerQueueService()

    monkeypatch.setattr(
        analysis_worker, "get_simple_analysis_service", lambda: simple_service
    )

    worker = analysis_worker.AnalysisWorker(worker_id="worker-test")
    worker.queue_service = queue_service

    await worker._process_task(
        {
            "id": "task-1",
            "user": "user-1",
            "symbol": "600519",
            "parameters": {
                "market_type": "A股",
                "research_depth": "标准",
                "quick_analysis_model": None,
                "deep_analysis_model": None,
            },
        }
    )

    assert simple_service.calls == [
        {
            "task_id": "task-1",
            "user_id": "user-1",
            "symbol": "600519",
            "market_type": "A股",
        }
    ]
    assert simple_service.status_updates == [
        ("task-1", analysis_worker.AnalysisStatus.PROCESSING, 10)
    ]
    assert queue_service.acked == [("task-1", True)]


@pytest.mark.asyncio
async def test_worker_acks_failed_when_memory_status_missing_but_persisted_status_failed(
    monkeypatch,
):
    simple_service = _WorkerSimpleService(status=None)
    queue_service = _WorkerQueueService()

    monkeypatch.setattr(
        analysis_worker, "get_simple_analysis_service", lambda: simple_service
    )

    worker = analysis_worker.AnalysisWorker(worker_id="worker-test")
    worker.queue_service = queue_service

    async def persisted_status(task_id):
        assert task_id == "task-1"
        return "failed"

    monkeypatch.setattr(worker, "_get_persisted_task_status", persisted_status)

    await worker._process_task(
        {
            "id": "task-1",
            "user": "user-1",
            "symbol": "600519",
            "parameters": {
                "market_type": "A股",
                "research_depth": "标准",
                "quick_analysis_model": None,
                "deep_analysis_model": None,
            },
        }
    )

    assert queue_service.acked == [("task-1", False)]
