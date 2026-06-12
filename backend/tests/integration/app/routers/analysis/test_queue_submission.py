from __future__ import annotations

import pytest

from app.worker import analysis as analysis_worker


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
