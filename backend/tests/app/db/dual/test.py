import logging

import pytest

from app.db.dual import (
    DualWriteBatchResult,
    DualWriteResult,
    dual_write_hot_document,
    dual_write_hot_documents,
    log_mongo_only_write,
)


@pytest.mark.asyncio
async def test_dual_write_skips_when_disabled():
    result = await dual_write_hot_document(
        "market_quotes",
        {"code": "000001", "source": "akshare"},
        enabled=False,
    )

    assert result == DualWriteResult(status="skipped", collection="market_quotes", reason="disabled")


@pytest.mark.asyncio
async def test_dual_write_executes_known_hot_collection():
    session = FakeSession()

    result = await dual_write_hot_document(
        "market_quotes",
        {"code": "000001", "source": "akshare"},
        session_factory=lambda: session,
        enabled=True,
    )

    assert result == DualWriteResult(status="written", collection="market_quotes", reason="")
    assert len(session.executed) == 1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_dual_write_logs_collection_status_and_legacy_id(caplog):
    session = FakeSession()
    logger = logging.getLogger("app.db.dual")
    caplog.set_level(logging.INFO, logger=logger.name)
    logger.addHandler(caplog.handler)

    try:
        result = await dual_write_hot_document(
            "market_quotes",
            {"code": "000001", "source": "akshare"},
            session_factory=lambda: session,
            enabled=True,
        )
    finally:
        logger.removeHandler(caplog.handler)

    assert result.status == "written"
    assert "PostgreSQL dual-write" in caplog.text
    assert "collection=market_quotes" in caplog.text
    assert "status=written" in caplog.text
    assert "legacy_ids=market_quotes:akshare:000001" in caplog.text
    assert "reason=" in caplog.text
    assert any(record.levelno == logging.INFO for record in caplog.records)


@pytest.mark.asyncio
async def test_dual_write_skips_unknown_collection():
    result = await dual_write_hot_document(
        "unmigrated_collection",
        {"value": 1},
        enabled=True,
    )

    assert result == DualWriteResult(
        status="skipped",
        collection="unmigrated_collection",
        reason="unsupported_collection",
    )


@pytest.mark.asyncio
async def test_dual_write_fail_open_returns_failure_for_uninitialized_session():
    def missing_session_factory():
        raise RuntimeError("PostgreSQL session factory is not initialized")

    result = await dual_write_hot_document(
        "market_quotes",
        {"code": "000001", "source": "akshare"},
        session_factory=missing_session_factory,
        enabled=True,
        fail_open=True,
    )

    assert result.status == "failed"
    assert result.collection == "market_quotes"
    assert "not initialized" in result.reason


@pytest.mark.asyncio
async def test_dual_write_fail_open_logs_reason_and_legacy_id(caplog):
    def missing_session_factory():
        raise RuntimeError("PostgreSQL session factory is not initialized")

    logger = logging.getLogger("app.db.dual")
    caplog.set_level(logging.WARNING, logger=logger.name)
    logger.addHandler(caplog.handler)

    try:
        result = await dual_write_hot_document(
            "market_quotes",
            {"code": "000001", "source": "akshare"},
            session_factory=missing_session_factory,
            enabled=True,
            fail_open=True,
        )
    finally:
        logger.removeHandler(caplog.handler)

    assert result.status == "failed"
    assert "collection=market_quotes" in caplog.text
    assert "status=failed" in caplog.text
    assert "legacy_ids=market_quotes:akshare:000001" in caplog.text
    assert "reason=PostgreSQL session factory is not initialized" in caplog.text


@pytest.mark.asyncio
async def test_dual_write_fail_closed_raises_for_uninitialized_session():
    def missing_session_factory():
        raise RuntimeError("PostgreSQL session factory is not initialized")

    with pytest.raises(RuntimeError, match="not initialized"):
        await dual_write_hot_document(
            "market_quotes",
            {"code": "000001", "source": "akshare"},
            session_factory=missing_session_factory,
            enabled=True,
            fail_open=False,
        )


@pytest.mark.asyncio
async def test_dual_write_batch_executes_with_single_commit():
    session = FakeSession()

    result = await dual_write_hot_documents(
        "market_quotes",
        [
            {"code": "000001", "source": "akshare"},
            {"code": "000002", "source": "akshare"},
        ],
        session_factory=lambda: session,
        enabled=True,
    )

    assert result == DualWriteBatchResult(
        status="written",
        collection="market_quotes",
        attempted=2,
        written=2,
        reason="",
    )
    assert len(session.executed) == 2
    assert session.commits == 1


@pytest.mark.asyncio
async def test_dual_write_batch_skips_when_disabled():
    result = await dual_write_hot_documents(
        "market_quotes",
        [{"code": "000001", "source": "akshare"}],
        enabled=False,
    )

    assert result == DualWriteBatchResult(
        status="skipped",
        collection="market_quotes",
        attempted=1,
        written=0,
        reason="disabled",
    )


def test_log_mongo_only_write_warns(caplog):
    logger = logging.getLogger("app.db.dual")
    caplog.set_level(logging.WARNING, logger=logger.name)
    logger.addHandler(caplog.handler)

    try:
        result = log_mongo_only_write("sync_status", "pending_postgres_status_table")
    finally:
        logger.removeHandler(caplog.handler)

    assert result == DualWriteResult(
        status="skipped",
        collection="sync_status",
        reason="pending_postgres_status_table",
    )
    assert "Mongo-only write retained during PostgreSQL migration" in caplog.text
    assert "sync_status" in caplog.text


class FakeSession:
    def __init__(self):
        self.executed = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None
