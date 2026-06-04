import importlib
import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List


def test_enhanced_screening_enriches_from_db(monkeypatch):
    # Late import to patch module symbols correctly
    EnhancedScreeningService = getattr(importlib.import_module('app.services.screening.enhanced'), 'EnhancedScreeningService')

    # Fake DB layer
    class FakeCursor:
        def __init__(self, docs: List[Dict[str, Any]]):
            self._docs = docs

        async def to_list(self, length: int):
            return self._docs

    class FakeColl:
        def __init__(self, docs):
            self._docs = docs

        def find(self, query, projection=None):
            return FakeCursor(self._docs)

    class FakeDB:
        def __init__(self, docs):
            self._coll = FakeColl(docs)

        def __getitem__(self, name: str):
            return self._coll

    # Prepare quotes in DB for codes 000001, 600000
    quotes_docs = [
        {"code": "000001", "close": 10.5, "pct_chg": 1.2, "amount": 1.23e8},
        {"code": "600000", "close": 9.9, "pct_chg": -0.5, "amount": 8.76e7},
    ]

    # Patch get_mongo_db used inside enhanced_screening_service module
    ess_mod = importlib.import_module('app.services.screening.enhanced')

    def _fake_get_mongo_db():
        return FakeDB(quotes_docs)

    monkeypatch.setattr(ess_mod, "get_mongo_db", _fake_get_mongo_db, raising=True)

    # Patch condition analysis to force DB path
    def _fake_analyze(_self, _conditions):
        return {"can_use_database": True, "needs_technical_indicators": False}

    monkeypatch.setattr(EnhancedScreeningService, "_analyze_conditions", _fake_analyze, raising=True)

    # Patch db_service.screen_stocks to return minimal items with codes
    class _FakeDbService:
        async def screen_stocks(self, conditions, limit, offset, order_by):
            items = [
                {"code": "1", "name": "平安银行"},
                {"code": "600000", "name": "浦发银行"},
                {"code": "300750", "name": "宁德时代"},  # not present in quotes -> stays None
            ]
            total = len(items)
            return items, total

    async def _run():
        svc = EnhancedScreeningService()
        svc.db_service = _FakeDbService()
        res = await svc.screen_stocks(conditions=[])
        items = res["items"]
        # Map by code for assertion
        by_code = {str(it["code"]).zfill(6): it for it in items}
        assert by_code["000001"]["close"] == 10.5
        assert by_code["000001"]["pct_chg"] == 1.2
        assert by_code["600000"]["amount"] == 8.76e7
        # Code not present in DB remains without enrichment
        assert "close" not in by_code["300750"] or by_code["300750"]["close"] is None

    asyncio.run(_run())


def test_quotes_ingestion_run_once_writes_bulk(monkeypatch):
    QuotesIngestionService = getattr(importlib.import_module('app.services.quotes.ingestion'), 'QuotesIngestionService')
    qis_mod = importlib.import_module('app.services.quotes.ingestion')

    # Fake DataSourceManager to avoid external calls
    class _FakeManager:
        def get_realtime_quotes_with_fallback(self):
            return {
                "000001": {"close": 10.1, "pct_chg": 0.1, "amount": 1.0e8},
                "600000": {"close": 9.8, "pct_chg": -0.3, "amount": 7.5e7},
            }, "fake"

    monkeypatch.setattr(qis_mod, "DataSourceManager", _FakeManager, raising=True)

    # Capture bulk_write ops
    class _FakeResult:
        def __init__(self, upserted):
            self.matched_count = 0
            self.modified_count = 0
            self.upserted_ids = {i: None for i in range(upserted)}

    class _FakeColl:
        def __init__(self):
            self.last_ops = None
            self.last_update = None

        async def create_index(self, *args, **kwargs):
            return "ok"

        async def bulk_write(self, ops, ordered=False):
            self.last_ops = ops
            return _FakeResult(len(ops))

        async def update_one(self, query, update, upsert=False):
            self.last_update = (query, update, upsert)
            return SimpleNamespace(modified_count=1, upserted_id=None)

    class _FakeDB:
        def __init__(self):
            self._coll = _FakeColl()

        def __getitem__(self, name: str):
            return self._coll

    fake_db = _FakeDB()

    def _fake_get_mongo_db():
        return fake_db

    monkeypatch.setattr(qis_mod, "get_mongo_db", _fake_get_mongo_db, raising=True)
    dual_write_document_calls = []
    dual_write_documents_calls = []

    async def _fake_dual_write_document(collection, document):
        dual_write_document_calls.append((collection, document))
        return SimpleNamespace(status="success", reason=None)

    async def _fake_dual_write_documents(collection, documents):
        dual_write_documents_calls.append((collection, documents))
        return SimpleNamespace(status="success", reason=None)

    monkeypatch.setattr(qis_mod, "dual_write_hot_document", _fake_dual_write_document, raising=True)
    monkeypatch.setattr(qis_mod, "dual_write_hot_documents", _fake_dual_write_documents, raising=True)

    async def _run():
        svc = QuotesIngestionService()
        # Force trading time to True
        monkeypatch.setattr(QuotesIngestionService, "_is_trading_time", lambda self, now=None: True, raising=True)
        await svc.run_once()
        # Verify that two upsert operations were generated
        assert fake_db._coll.last_ops is not None
        assert len(fake_db._coll.last_ops) == 2
        assert dual_write_documents_calls[0][0] == "market_quotes"
        assert [doc["code"] for doc in dual_write_documents_calls[0][1]] == ["000001", "600000"]
        assert all(doc["source"] == "fake" for doc in dual_write_documents_calls[0][1])
        assert dual_write_document_calls[0][0] == "quotes_ingestion_status"
        assert dual_write_document_calls[0][1]["job"] == "quotes_ingestion"
        assert dual_write_document_calls[0][1]["success"] is True

    asyncio = importlib.import_module('asyncio')
    asyncio.run(_run())


def test_quotes_ingestion_status_dual_writes(monkeypatch):
    QuotesIngestionService = getattr(importlib.import_module('app.services.quotes.ingestion'), 'QuotesIngestionService')
    qis_mod = importlib.import_module('app.services.quotes.ingestion')

    class _FakeStatusCollection:
        def __init__(self):
            self.update_calls = []

        async def update_one(self, query, update, upsert=False):
            self.update_calls.append((query, update, upsert))
            return SimpleNamespace(modified_count=1, upserted_id=None)

    class _FakeDB:
        def __init__(self):
            self.status = _FakeStatusCollection()

        def __getitem__(self, name: str):
            assert name == "quotes_ingestion_status"
            return self.status

    fake_db = _FakeDB()
    dual_write_calls = []

    def _fake_get_mongo_db():
        return fake_db

    async def _fake_dual_write(collection, document):
        dual_write_calls.append((collection, document))
        return SimpleNamespace(status="success", reason=None)

    monkeypatch.setattr(qis_mod, "get_mongo_db", _fake_get_mongo_db, raising=True)
    monkeypatch.setattr(qis_mod, "dual_write_hot_document", _fake_dual_write, raising=True)

    async def _run():
        svc = QuotesIngestionService()
        await svc._record_sync_status(
            success=False,
            source="akshare_eastmoney",
            records_count=0,
            error_msg="API limit",
        )

    asyncio.run(_run())

    assert fake_db.status.update_calls
    assert dual_write_calls[0][0] == "quotes_ingestion_status"
    assert dual_write_calls[0][1]["job"] == "quotes_ingestion"
    assert dual_write_calls[0][1]["success"] is False
    assert dual_write_calls[0][1]["data_source"] == "akshare_eastmoney"
    assert dual_write_calls[0][1]["error_message"] == "API limit"
