from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.services import scheduler_service


@pytest.mark.asyncio
async def test_record_job_action_dual_writes_scheduler_history(monkeypatch):
    service = scheduler_service.SchedulerService.__new__(scheduler_service.SchedulerService)
    service.scheduler = FakeScheduler()
    service.db = SimpleNamespace(scheduler_history=FakeAsyncCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(scheduler_service, "dual_write_hot_document", fake_dual_write)

    await service._record_job_action("daily_sync", "trigger", "success")

    assert dual_write_calls[0][0] == "scheduler_history"
    assert dual_write_calls[0][1]["_id"] == service.db.scheduler_history.inserted_id
    assert dual_write_calls[0][1]["job_id"] == "daily_sync"
    assert dual_write_calls[0][1]["action"] == "trigger"


@pytest.mark.asyncio
async def test_update_job_metadata_dual_writes_scheduler_metadata(monkeypatch):
    service = scheduler_service.SchedulerService.__new__(scheduler_service.SchedulerService)
    service.scheduler = FakeScheduler()
    service.db = SimpleNamespace(scheduler_metadata=FakeAsyncCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(scheduler_service, "dual_write_hot_document", fake_dual_write)

    assert await service.update_job_metadata("daily_sync", "每日同步", "盘后同步") is True

    assert dual_write_calls[0][0] == "scheduler_metadata"
    assert dual_write_calls[0][1]["job_id"] == "daily_sync"
    assert dual_write_calls[0][1]["display_name"] == "每日同步"


@pytest.mark.asyncio
async def test_record_job_execution_dual_writes_insert_and_completion_update(monkeypatch):
    running_id = ObjectId()
    service = scheduler_service.SchedulerService.__new__(scheduler_service.SchedulerService)
    service.scheduler = FakeScheduler()
    service.db = SimpleNamespace(
        scheduler_executions=FakeAsyncCollection(existing={"_id": running_id, "job_id": "daily_sync", "status": "running"})
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="written", reason="")

    monkeypatch.setattr(scheduler_service, "dual_write_hot_document", fake_dual_write)

    await service._record_job_execution("daily_sync", "running", progress=10)
    await service._record_job_execution("daily_sync", "success", execution_time=1.2, progress=100)

    assert dual_write_calls[0][0] == "scheduler_executions"
    assert dual_write_calls[0][1]["status"] == "running"
    assert dual_write_calls[1][0] == "scheduler_executions"
    assert dual_write_calls[1][1]["_id"] == running_id
    assert dual_write_calls[1][1]["status"] == "success"


class FakeScheduler:
    def get_job(self, job_id):
        return SimpleNamespace(id=job_id, name="每日同步")


class FakeAsyncCollection:
    def __init__(self, existing=None):
        self.inserted_id = ObjectId()
        self.existing = existing

    async def insert_one(self, document):
        self.inserted = document
        return SimpleNamespace(inserted_id=self.inserted_id)

    async def update_one(self, *_args, **_kwargs):
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)

    async def find_one(self, *_args, **_kwargs):
        existing = self.existing
        self.existing = None
        return existing
