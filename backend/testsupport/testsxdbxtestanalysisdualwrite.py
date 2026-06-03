from types import SimpleNamespace

import pytest

from app.models.analysismodels import AnalysisStatus
from app.services.analysis import statusupdateutils
from app.services import simpleanalysisservice
from app.routers import analysisrouter as analysis_router
from app.routers import reports as reports_router


@pytest.mark.asyncio
async def test_analysis_status_update_dual_writes_task(monkeypatch):
    fake_db = SimpleNamespace(analysis_tasks=FakeUpdateCollection())
    redis_payloads = []
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(status_update_utils, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(
        status_update_utils,
        "get_redis_service",
        lambda: FakeRedisService(redis_payloads),
    )
    monkeypatch.setattr(status_update_utils, "dual_write_hot_document", fake_dual_write)

    await status_update_utils.perform_update_task_status(
        "task-1",
        AnalysisStatus.PROCESSING,
        25,
    )

    assert fake_db.analysis_tasks.updates[0][0] == {"task_id": "task-1"}
    assert dual_write_calls[0][0] == "analysis_tasks"
    assert dual_write_calls[0][1]["task_id"] == "task-1"
    assert dual_write_calls[0][1]["status"] == AnalysisStatus.PROCESSING
    assert dual_write_calls[0][1]["progress"] == 25
    assert "updated_at" in dual_write_calls[0][1]
    assert redis_payloads


@pytest.mark.asyncio
async def test_web_style_analysis_result_dual_writes_report_and_task(monkeypatch):
    fake_db = SimpleNamespace(
        analysis_reports=FakeInsertCollection(inserted_id="report-mongo-id"),
        analysis_tasks=FakeUpdateCollection(),
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(simple_analysis_service, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(simple_analysis_service, "dual_write_hot_document", fake_dual_write)

    service = simple_analysis_service.SimpleAnalysisService.__new__(
        simple_analysis_service.SimpleAnalysisService
    )
    await service._save_analysis_result_web_style(
        "task-1",
        {
            "stock_symbol": "AAPL",
            "summary": "Apple analysis summary",
            "recommendation": "buy",
            "confidence_score": 0.82,
            "risk_level": "中等",
            "key_points": ["growth"],
            "execution_time": 12,
            "tokens_used": 345,
            "decision": {"action": "buy"},
            "state": {
                "market_report": "Market report content long enough",
                "fundamentals_report": "Fundamentals report content long enough",
            },
        },
    )

    assert fake_db.analysis_reports.documents[0]["task_id"] == "task-1"
    assert fake_db.analysis_reports.documents[0]["stock_symbol"] == "AAPL"
    assert fake_db.analysis_tasks.updates[0][0] == {"task_id": "task-1"}

    assert [call[0] for call in dual_write_calls] == [
        "analysis_reports",
        "analysis_tasks",
    ]
    assert dual_write_calls[0][1]["analysis_id"].startswith("AAPL_")
    assert dual_write_calls[0][1]["task_id"] == "task-1"
    assert dual_write_calls[0][1]["reports"]["market_report"] == (
        "Market report content long enough"
    )
    assert dual_write_calls[1][1]["task_id"] == "task-1"
    assert dual_write_calls[1][1]["result"]["analysis_id"] == dual_write_calls[0][1]["analysis_id"]
    assert dual_write_calls[1][1]["result"]["recommendation"] == "buy"


@pytest.mark.asyncio
async def test_mark_task_failed_route_dual_writes_task(monkeypatch):
    fake_db = SimpleNamespace(analysis_tasks=FakeUpdateCollection())
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(analysis_router, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(analysis_router, "dual_write_hot_document", fake_dual_write)
    monkeypatch.setattr(
        analysis_router,
        "get_simple_analysis_service",
        lambda: SimpleNamespace(memory_manager=FakeMemoryManager()),
    )

    result = await analysis_router.mark_task_as_failed("task-1", user={"id": "user-1"})

    assert result["success"] is True
    assert fake_db.analysis_tasks.updates[0][0] == {"task_id": "task-1"}
    assert dual_write_calls[0][0] == "analysis_tasks"
    assert dual_write_calls[0][1]["task_id"] == "task-1"
    assert dual_write_calls[0][1]["status"] == "failed"
    assert "completed_at" in dual_write_calls[0][1]


@pytest.mark.asyncio
async def test_delete_task_route_dual_writes_tombstone(monkeypatch):
    fake_db = SimpleNamespace(
        analysis_tasks=FakeDeleteCollection(
            {"task_id": "task-1", "status": "running", "user_id": "user-1"}
        )
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(analysis_router, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(analysis_router, "dual_write_hot_document", fake_dual_write)
    monkeypatch.setattr(
        analysis_router,
        "get_simple_analysis_service",
        lambda: SimpleNamespace(memory_manager=FakeMemoryManager()),
    )

    result = await analysis_router.delete_task("task-1", user={"id": "user-1"})

    assert result["success"] is True
    assert fake_db.analysis_tasks.deleted_queries == [{"task_id": "task-1"}]
    assert dual_write_calls[0][0] == "analysis_tasks"
    assert dual_write_calls[0][1]["task_id"] == "task-1"
    assert dual_write_calls[0][1]["status"] == "running"
    assert dual_write_calls[0][1]["deleted"] is True


@pytest.mark.asyncio
async def test_delete_report_route_dual_writes_tombstone(monkeypatch):
    fake_db = SimpleNamespace(
        analysis_reports=FakeDeleteCollection(
            {"analysis_id": "report-1", "task_id": "task-1", "summary": "report"}
        )
    )
    dual_write_calls = []

    async def fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))

    monkeypatch.setattr(reports_router, "get_mongo_db", lambda: fake_db)
    monkeypatch.setattr(reports_router, "dual_write_hot_document", fake_dual_write)

    result = await reports_router.delete_report("report-1", user={"id": "user-1"})

    assert result["success"] is True
    assert dual_write_calls[0][0] == "analysis_reports"
    assert dual_write_calls[0][1]["analysis_id"] == "report-1"
    assert dual_write_calls[0][1]["task_id"] == "task-1"
    assert dual_write_calls[0][1]["deleted"] is True


class FakeUpdateCollection:
    def __init__(self):
        self.updates = []

    async def update_one(self, *args, **kwargs):
        self.updates.append((args[0], args[1], kwargs))
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)


class FakeInsertCollection:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(document)
        return SimpleNamespace(inserted_id=self.inserted_id)


class FakeDeleteCollection:
    def __init__(self, document):
        self.document = document
        self.deleted_queries = []

    async def find_one(self, query):
        return self.document

    async def delete_one(self, query):
        self.deleted_queries.append(query)
        return SimpleNamespace(deleted_count=1)


class FakeMemoryManager:
    async def update_task_status(self, **_kwargs):
        return None

    async def remove_task(self, _task_id):
        return None


class FakeRedisService:
    def __init__(self, payloads):
        self.payloads = payloads

    async def set_json(self, *args, **kwargs):
        self.payloads.append((args, kwargs))
