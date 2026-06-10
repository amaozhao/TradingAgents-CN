from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import research_agent as research_agent_router
from app.services.research_agent import artifacts as artifacts_module
from app.services.research_agent import events as events_module
from app.services.research_agent.tools import files as files_module
from app.services.research_agent import sessions as sessions_module
from app.services.research_agent.context import ResearchPrincipal, ToolExecutionContext
from app.services.research_agent.events import ResearchEventService
from app.services.research_agent.registry import ResearchToolRegistry
from app.services.research_agent.sessions import ResearchSessionService


USER_A = {"id": "user-a", "username": "alice", "is_admin": False, "roles": []}
USER_B = {"id": "user-b", "username": "bob", "is_admin": False, "roles": []}


def _matches_query(document: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if document.get(key) != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self.documents = sorted(
            self.documents, key=lambda item: item.get(key, 0), reverse=reverse
        )
        return self

    def __aiter__(self):
        self._iter = iter(self.documents)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self):
        self.documents: list[dict[str, Any]] = []

    async def insert_one(self, document: dict[str, Any]):
        self.documents.append(dict(document))
        return type("FakeInsertResult", (), {"inserted_id": document.get("_id")})()

    async def find_one(self, query: dict[str, Any], *_args: Any, **_kwargs: Any):
        rows = [doc for doc in self.documents if _matches_query(doc, query)]
        return dict(rows[0]) if rows else None

    def find(self, query: dict[str, Any]):
        return FakeCursor([doc for doc in self.documents if _matches_query(doc, query)])

    async def count_documents(self, query: dict[str, Any]):
        return len([doc for doc in self.documents if _matches_query(doc, query)])

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]):
        for document in self.documents:
            if _matches_query(document, query):
                document.update(update.get("$set", {}))
                return type("FakeUpdateResult", (), {"modified_count": 1})()
        return type("FakeUpdateResult", (), {"modified_count": 0})()

    async def delete_many(self, query: dict[str, Any]):
        before = len(self.documents)
        self.documents = [
            document for document in self.documents if not _matches_query(document, query)
        ]
        return type("FakeDeleteResult", (), {"deleted_count": before - len(self.documents)})()


class FakeDb:
    def __init__(self):
        self.research_sessions = FakeCollection()
        self.research_messages = FakeCollection()
        self.research_events = FakeCollection()
        self.research_artifacts = FakeCollection()
        self.research_jobs = FakeCollection()
        self.research_attempts = FakeCollection()


class FakeUpload:
    def __init__(self, data: bytes, filename: str = "memo.txt", content_type: str = "text/plain"):
        self._file = BytesIO(data)
        self.filename = filename
        self.content_type = content_type

    async def read(self):
        return self._file.read()


class FakeSearchResponse:
    text = """
    <html>
      <a class="result__a" href="https://example.com/a">Alpha Result</a>
      <a class="result__snippet">First snippet</a>
      <a class="result__a" href="https://example.com/b">Beta Result</a>
      <a class="result__snippet">Second snippet</a>
    </html>
    """

    def raise_for_status(self):
        return None


class FakeSearchClient:
    def __init__(self, *_args: Any, **_kwargs: Any):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: Any):
        return None

    async def get(self, *_args: Any, **_kwargs: Any):
        return FakeSearchResponse()


@pytest.fixture()
def fake_db(monkeypatch):
    db = FakeDb()
    for module in (sessions_module, events_module, artifacts_module):
        monkeypatch.setattr(module, "get_postgres_db", lambda db=db: db)
    return db


def _principal(user: dict[str, Any], session_id: str | None = "session-files"):
    return ResearchPrincipal.from_user(user, session_id=session_id)


@pytest.mark.asyncio
async def test_upload_artifact_and_read_document_tool_are_owner_scoped(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = artifacts_module.ResearchArtifactService()

    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="文件会话"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]
    upload = await research_agent_router.upload_research_file(
        file=FakeUpload("交易 thesis and risk".encode("utf-8")),  # type: ignore[arg-type]
        session_id=session_id,
        current_user=USER_A,
    )
    artifact_id = upload["data"]["artifact_id"]
    fetched = await research_agent_router.get_research_artifact(
        artifact_id, current_user=USER_A
    )
    registry = ResearchToolRegistry.default()
    content = await registry.get("read_document").run(
        ToolExecutionContext(principal=_principal(USER_A), session_id=session_id),
        {"artifact_id": artifact_id},
    )
    missing = await registry.get("read_document").run(
        ToolExecutionContext(principal=_principal(USER_B), session_id=session_id),
        {"artifact_id": artifact_id},
    )

    assert fetched["data"]["payload"]["filename"] == "memo.txt"
    assert content["status"] == "completed"
    assert "thesis" in content["content"]
    assert missing["status"] == "not_found"


@pytest.mark.asyncio
async def test_read_document_accepts_inline_example_text(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()
    result = await registry.get("read_document").run(
        ToolExecutionContext(principal=_principal(USER_A), session_id="session-inline-doc"),
        {
            "filename": "energy-storage-note.md",
            "text": "Thesis: storage demand improves. Risks: price competition and weak IRR.",
        },
    )

    assert result["status"] == "completed"
    assert result["artifact_id"]
    assert result["filename"] == "energy-storage-note.md"
    assert "storage demand" in result["content"]


@pytest.mark.asyncio
async def test_read_url_blocks_local_targets(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()
    with pytest.raises(ValueError):
        await registry.get("read_url").run(
            ToolExecutionContext(principal=_principal(USER_A), session_id="session-files"),
            {"url": "http://127.0.0.1:5900/agent"},
        )


@pytest.mark.asyncio
async def test_upload_extracts_docx_and_basic_pdf_text(fake_db):
    _ = fake_db
    research_agent_router.session_service = ResearchSessionService()
    research_agent_router.event_service = ResearchEventService()
    research_agent_router.artifact_service = artifacts_module.ResearchArtifactService()
    created = await research_agent_router.create_research_session(
        research_agent_router.ResearchSessionCreateRequest(title="二进制文档"),
        current_user=USER_A,
    )
    session_id = created["data"]["session_id"]

    from docx import Document

    document = Document()
    document.add_paragraph("DOCX thesis and catalyst")
    docx_buffer = BytesIO()
    document.save(docx_buffer)
    docx_upload = await research_agent_router.upload_research_file(
        file=FakeUpload(
            docx_buffer.getvalue(),
            filename="memo.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),  # type: ignore[arg-type]
        session_id=session_id,
        current_user=USER_A,
    )
    pdf_upload = await research_agent_router.upload_research_file(
        file=FakeUpload(
            b"%PDF-1.4\n1 0 obj <<>> stream\nBT (PDF thesis and risk) Tj ET\nendstream\n%%EOF",
            filename="memo.pdf",
            content_type="application/pdf",
        ),  # type: ignore[arg-type]
        session_id=session_id,
        current_user=USER_A,
    )
    registry = ResearchToolRegistry.default()
    docx_content = await registry.get("read_document").run(
        ToolExecutionContext(principal=_principal(USER_A), session_id=session_id),
        {"artifact_id": docx_upload["data"]["artifact_id"]},
    )
    pdf_content = await registry.get("read_document").run(
        ToolExecutionContext(principal=_principal(USER_A), session_id=session_id),
        {"artifact_id": pdf_upload["data"]["artifact_id"]},
    )

    assert "DOCX thesis" in docx_content["content"]
    assert "PDF thesis" in pdf_content["content"]


@pytest.mark.asyncio
async def test_web_search_parses_results_and_stores_artifact(fake_db, monkeypatch):
    _ = fake_db
    monkeypatch.setattr(files_module.httpx, "AsyncClient", FakeSearchClient)
    registry = ResearchToolRegistry.default()

    result = await registry.get("web_search").run(
        ToolExecutionContext(principal=_principal(USER_A), session_id="session-files"),
        {"query": "alpha trading", "limit": 2},
    )

    assert result["status"] == "completed"
    assert result["results"][0]["title"] == "Alpha Result"
    assert result["artifact_id"]
    assert fake_db.research_artifacts.documents[0]["artifact_type"] == "web_search"


@pytest.mark.asyncio
async def test_run_and_shadow_artifact_routes_are_owner_scoped(fake_db):
    _ = fake_db
    research_agent_router.artifact_service = artifacts_module.ResearchArtifactService()
    service = research_agent_router.artifact_service
    await service.create_artifact(
        session_id="session-files",
        user_id=USER_A["id"],
        artifact_type="run",
        payload={"run_id": "run-1", "metrics": {"sharpe": 1.2}},
    )
    await service.create_artifact(
        session_id="session-files",
        user_id=USER_A["id"],
        artifact_type="run_code",
        payload={"run_id": "run-1", "code": "print('run')"},
    )
    await service.create_artifact(
        session_id="session-files",
        user_id=USER_A["id"],
        artifact_type="run_pine",
        payload={"run_id": "run-1", "pine": "strategy('run')"},
    )
    await service.create_artifact(
        session_id="session-files",
        user_id=USER_A["id"],
        artifact_type="shadow_report",
        payload={"shadow_id": "shadow-1", "summary": "shadow report"},
    )

    runs = await research_agent_router.list_research_runs(current_user=USER_A)
    run = await research_agent_router.get_research_run("run-1", current_user=USER_A)
    code = await research_agent_router.get_research_run_code("run-1", current_user=USER_A)
    pine = await research_agent_router.get_research_run_pine("run-1", current_user=USER_A)
    shadow = await research_agent_router.get_shadow_report("shadow-1", current_user=USER_A)

    assert len(runs["data"]) == 1
    assert run["data"]["payload"]["metrics"]["sharpe"] == 1.2
    assert code["data"]["payload"]["code"] == "print('run')"
    assert pine["data"]["payload"]["pine"] == "strategy('run')"
    assert shadow["data"]["payload"]["summary"] == "shadow report"
    with pytest.raises(HTTPException):
        await research_agent_router.get_research_run("run-1", current_user=USER_B)


@pytest.mark.asyncio
async def test_shadow_tools_create_current_project_artifacts_without_fabricating_data(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=_principal(USER_A),
        session_id="session-files",
    )

    strategy = await registry.get("extract_shadow_strategy").run(
        context,
        {
            "description": "buy momentum breakouts after volume expansion; exit failed retests",
            "risk_rules": ["max loss 2%"],
        },
    )
    missing_backtest = await registry.get("run_shadow_backtest").run(
        context, {"strategy_id": strategy["strategy_id"]}
    )
    backtest = await registry.get("run_shadow_backtest").run(
        context,
        {"strategy_id": strategy["strategy_id"], "returns": [0.02, -0.01, 0.03]},
    )
    report = await registry.get("render_shadow_report").run(
        context,
        {
            "strategy_id": strategy["strategy_id"],
            "backtest_id": backtest["backtest_id"],
            "summary": "Momentum shadow report",
        },
    )
    signals = await registry.get("scan_shadow_signals").run(
        context, {"signals": [{"symbol": "300750.SZ", "score": 0.8}]}
    )

    assert strategy["status"] == "completed"
    assert missing_backtest["status"] == "config_required"
    assert backtest["metrics"]["observations"] == 3
    assert report["status"] == "completed"
    assert signals["count"] == 1
    assert {item["artifact_type"] for item in fake_db.research_artifacts.documents} >= {
        "shadow_strategy",
        "shadow_backtest",
        "shadow_report",
    }


@pytest.mark.asyncio
async def test_trade_journal_tool_analyzes_text_and_owned_uploads(fake_db):
    _ = fake_db
    registry = ResearchToolRegistry.default()
    context = ToolExecutionContext(
        principal=_principal(USER_A),
        session_id="session-files",
    )
    direct = await registry.get("analyze_trade_journal").run(
        context,
        {
            "text": "\n".join(
                [
                    "2026-01-01 300750.SZ pnl +1200 followed plan",
                    "2026-01-02 TSLA loss 300 stopped out; discipline breach",
                    "2026-01-03 AAPL 盈亏：0",
                ]
            )
        },
    )
    artifact = await artifacts_module.ResearchArtifactService().create_artifact(
        session_id="session-files",
        user_id=USER_A["id"],
        artifact_type="upload",
        payload={"filename": "journal.txt", "text": "MSFT profit 500\nNVDA 违规 pnl -250"},
    )
    uploaded = await registry.get("analyze_trade_journal").run(
        context,
        {"artifact_id": artifact["artifact_id"]},
    )
    missing = await registry.get("analyze_trade_journal").run(
        ToolExecutionContext(principal=_principal(USER_B), session_id="session-files"),
        {"artifact_id": artifact["artifact_id"]},
    )

    assert direct["status"] == "completed"
    assert direct["metrics"]["trades_with_pnl"] == 3
    assert direct["metrics"]["wins"] == 1
    assert direct["metrics"]["losses"] == 1
    assert direct["metrics"]["risk_flag_count"] == 1
    assert direct["artifact_id"]
    assert uploaded["metrics"]["total_pnl"] == 250
    assert missing["status"] == "config_required"
    assert missing["source"]["status"] == "not_found"
