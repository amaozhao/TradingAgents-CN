from __future__ import annotations

import pytest
from fastapi.responses import StreamingResponse

from app.routers import sse


class _Repository:
    def __init__(self, batch: dict[str, object] | None) -> None:
        self.batch = batch
        self.calls: list[tuple[str, str]] = []

    async def get_batch(self, batch_id: str, user_id: str) -> dict[str, object] | None:
        self.calls.append((batch_id, user_id))
        return self.batch


class _LegacyQueue:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_batch(self, batch_id: str) -> dict[str, object] | None:
        self.calls.append(batch_id)
        raise AssertionError("workflow batches must not require legacy queue lookup")


@pytest.mark.asyncio
async def test_stream_batch_progress_accepts_workflow_repository_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _Repository(
        {
            "batch_id": "batch-1",
            "user_id": "user-1",
            "total_tasks": 1,
            "tasks": [{"task_id": "task-1", "status": "processing"}],
        }
    )
    queue = _LegacyQueue()
    monkeypatch.setattr(sse, "BatchRepository", lambda: repository)

    response = await sse.stream_batch_progress(
        "batch-1",
        {"id": "user-1"},
        queue,
    )

    assert isinstance(response, StreamingResponse)
    assert repository.calls == [("batch-1", "user-1")]
    assert queue.calls == []
