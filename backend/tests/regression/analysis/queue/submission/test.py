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
async def test_batch_analysis_submission_only_enqueues_work(queue_submission_fakes):
    _, queue_service = queue_submission_fakes

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
    assert [item["symbol"] for item in queue_service.enqueued] == ["600519", "000001"]
    assert [item["task_id"] for item in queue_service.enqueued] == ["task-1", "task-2"]
    assert all(
        item["batch_id"] == result["data"]["batch_id"]
        for item in queue_service.enqueued
    )


class _WorkerQueueService:
    def __init__(self) -> None:
        self.acked: list[tuple[str, bool]] = []

    async def ack_task(self, task_id: str, success: bool):
        self.acked.append((task_id, success))


class _WorkerSimpleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

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
        return {"task_id": task_id, "status": "completed"}


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
    assert queue_service.acked == [("task-1", True)]
