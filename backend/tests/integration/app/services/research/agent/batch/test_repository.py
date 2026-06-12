from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Mapping

import pytest

from app.services.research.agent.batch import repository as batch_repository
from app.services.research.agent.batch.state import BatchChildState, BatchWorkflowState


class _InsertManyResult:
    def __init__(self, inserted_ids: list[str]) -> None:
        self.inserted_ids = inserted_ids


class _UpdateResult:
    def __init__(self, matched_count: int, modified_count: int) -> None:
        self.matched_count = matched_count
        self.modified_count = modified_count


class _Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        if length is None:
            return deepcopy(self._documents)
        return deepcopy(self._documents[:length])


class _Collection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.updates: list[tuple[dict[str, Any], dict[str, Any]]] = []

    async def insert_one(self, document: Mapping[str, Any]) -> Any:
        stored = deepcopy(dict(document))
        self.documents.append(stored)
        return type("InsertOneResult", (), {"inserted_id": stored.get("_id")})()

    async def insert_many(self, documents: Iterable[Mapping[str, Any]]) -> _InsertManyResult:
        inserted_ids: list[str] = []
        for document in documents:
            stored = deepcopy(dict(document))
            self.documents.append(stored)
            inserted_ids.append(str(stored.get("_id") or stored.get("task_id") or ""))
        return _InsertManyResult(inserted_ids)

    async def find_one(self, query: Mapping[str, Any]) -> dict[str, Any] | None:
        for document in self.documents:
            if _matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query: Mapping[str, Any]) -> _Cursor:
        return _Cursor([document for document in self.documents if _matches(document, query)])

    async def update_one(
        self,
        query: Mapping[str, Any],
        update: Mapping[str, Mapping[str, Any]],
    ) -> _UpdateResult:
        self.updates.append((deepcopy(dict(query)), deepcopy(dict(update))))
        for document in self.documents:
            if not _matches(document, query):
                continue
            set_values = update.get("$set", {})
            document.update(deepcopy(dict(set_values)))
            return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)


class _Database:
    def __init__(self) -> None:
        self.analysis_batches = _Collection()
        self.analysis_tasks = _Collection()


def _matches(document: Mapping[str, Any], query: Mapping[str, Any]) -> bool:
    return all(document.get(key) == value for key, value in query.items())


def _state() -> BatchWorkflowState:
    return BatchWorkflowState(
        batch_id="batch-1",
        user_id="user-1",
        title="批量分析",
        description="核心持仓",
        status="pending",
        parameters={
            "market_type": "A股",
            "analysis_date": "2026-06-12",
            "research_depth": "标准",
            "selected_analysts": ["market", "fundamentals"],
            "include_sentiment": True,
            "include_risk": True,
            "language": "zh-CN",
        },
        children=[
            BatchChildState(symbol="600036", stock_code="600036", task_id="task-1"),
            BatchChildState(symbol="000001", stock_code="000001", task_id="task-2"),
        ],
        created_at=datetime(2026, 6, 12, 10, 0, 0),
    )


@pytest.fixture
def db() -> _Database:
    return _Database()


@pytest.fixture(autouse=True)
def dual_write(monkeypatch):
    calls: list[tuple[str, object]] = []

    async def fake_hot_document(collection: str, document: dict[str, Any]):
        calls.append((collection, deepcopy(document)))

    async def fake_hot_documents(collection: str, documents: list[dict[str, Any]]):
        calls.append((collection, deepcopy(documents)))

    monkeypatch.setattr(batch_repository, "dual_write_hot_document", fake_hot_document)
    monkeypatch.setattr(batch_repository, "dual_write_hot_documents", fake_hot_documents)
    return calls


@pytest.mark.asyncio
async def test_save_submitted_batch_writes_batch_and_child_task_documents(
    db: _Database,
    dual_write: list[tuple[str, object]],
) -> None:
    repo = batch_repository.BatchRepository(db=db)

    await repo.save_submitted_batch(_state())

    assert len(db.analysis_batches.documents) == 1
    batch = db.analysis_batches.documents[0]
    assert batch["batch_id"] == "batch-1"
    assert batch["user_id"] == "user-1"
    assert batch["title"] == "批量分析"
    assert batch["description"] == "核心持仓"
    assert batch["status"] == "pending"
    assert batch["total_tasks"] == 2
    assert batch["completed_tasks"] == 0
    assert batch["failed_tasks"] == 0
    assert batch["cancelled_tasks"] == 0
    assert batch["progress"] == 0
    assert batch["parameters"]["market_type"] == "A股"
    assert batch["results_summary"]["mapping"] == {
        "600036": "task-1",
        "000001": "task-2",
    }

    assert [task["task_id"] for task in db.analysis_tasks.documents] == [
        "task-1",
        "task-2",
    ]
    first_task = db.analysis_tasks.documents[0]
    assert first_task["batch_id"] == "batch-1"
    assert first_task["user_id"] == "user-1"
    assert first_task["symbol"] == "600036"
    assert first_task["stock_code"] == "600036"
    assert first_task["stock_symbol"] == "600036"
    assert first_task["status"] == "pending"
    assert first_task["progress"] == 0
    assert first_task["parameters"]["selected_analysts"] == ["market", "fundamentals"]
    assert ("analysis_batches", batch) in dual_write
    assert dual_write[-1][0] == "analysis_tasks"


@pytest.mark.asyncio
async def test_get_batch_is_scoped_to_owner(db: _Database) -> None:
    repo = batch_repository.BatchRepository(db=db)
    await repo.save_submitted_batch(_state())

    assert await repo.get_batch("batch-1", "other-user") is None
    batch = await repo.get_batch("batch-1", "user-1")

    assert batch is not None
    assert batch["batch_id"] == "batch-1"
    assert [task["task_id"] for task in batch["tasks"]] == ["task-1", "task-2"]


@pytest.mark.asyncio
async def test_update_child_is_scoped_to_batch_and_owner(db: _Database) -> None:
    repo = batch_repository.BatchRepository(db=db)
    state = _state()
    await repo.save_submitted_batch(state)
    child = BatchChildState(
        symbol="600036",
        stock_code="600036",
        task_id="task-1",
        status="completed",
        progress=100,
        analysis_id="analysis-1",
        report_url="/reports/view/task-1",
    )

    result = await repo.update_child("batch-1", "user-1", child)

    assert result is True
    updated = await db.analysis_tasks.find_one({"task_id": "task-1", "user_id": "user-1"})
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["progress"] == 100
    assert updated["analysis_id"] == "analysis-1"
    assert updated["report_url"] == "/reports/view/task-1"
    query, _ = db.analysis_tasks.updates[-1]
    assert query == {"batch_id": "batch-1", "user_id": "user-1", "task_id": "task-1"}


@pytest.mark.asyncio
async def test_update_batch_aggregate_writes_legacy_summary_fields(db: _Database) -> None:
    repo = batch_repository.BatchRepository(db=db)
    state = _state()
    await repo.save_submitted_batch(state)
    state.children[0].status = "completed"
    state.children[0].progress = 100
    state.children[1].status = "failed"
    state.children[1].progress = 100
    state.children[1].error = "model failed"

    result = await repo.update_batch_aggregate(state)

    assert result is True
    batch = await db.analysis_batches.find_one(
        {"batch_id": "batch-1", "user_id": "user-1"}
    )
    assert batch is not None
    assert batch["status"] == "partial_success"
    assert batch["completed_tasks"] == 1
    assert batch["failed_tasks"] == 1
    assert batch["progress"] == 100
    assert batch["results_summary"]["mapping"] == {
        "600036": "task-1",
        "000001": "task-2",
    }
    assert batch["results_summary"]["children"][1]["error"] == "model failed"
