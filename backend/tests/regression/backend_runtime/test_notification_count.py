from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

loaded_app = sys.modules.get("app")
loaded_app_file = str(getattr(loaded_app, "__file__", "") or "")
loaded_app_paths = [
    str(path) for path in getattr(loaded_app, "__path__", []) if path is not None
]
if "/tests/app" in loaded_app_file or any("/tests/app" in path for path in loaded_app_paths):
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]

from app.db.store.collection import _can_count_in_database
from app.services.notification import NotificationsService


def test_simple_equality_query_can_count_in_database() -> None:
    assert _can_count_in_database({"user_id": "admin", "status": "unread"})


def test_complex_query_keeps_python_match_fallback() -> None:
    assert not _can_count_in_database({"created_at": {"$lt": "2026-06-05"}})
    assert not _can_count_in_database({"metadata.source": "analysis"})
    assert not _can_count_in_database({"$or": [{"status": "unread"}]})


class _ScalarResult:
    def scalar_one(self) -> int:
        return 7


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, _statement):
        return _ScalarResult()


@pytest.mark.asyncio
async def test_unread_count_uses_fast_sql_path(monkeypatch: pytest.MonkeyPatch) -> None:
    service = NotificationsService()

    monkeypatch.setattr(
        "app.services.notification.get_session_factory", lambda: lambda: _Session()
    )

    def fail_get_postgres_db():
        raise AssertionError("document-store fallback should not be used")

    monkeypatch.setattr("app.services.notification.get_postgres_db", fail_get_postgres_db)

    assert await service.unread_count("admin") == 7


@pytest.mark.asyncio
async def test_unread_count_falls_back_to_document_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = NotificationsService()

    def fail_session_factory():
        raise RuntimeError("session unavailable")

    class Collection:
        async def count_documents(self, query):
            assert query == {"user_id": "admin", "status": "unread"}
            return 3

    class Database:
        def __getitem__(self, name):
            assert name == "notifications"
            return Collection()

    monkeypatch.setattr("app.services.notification.get_session_factory", fail_session_factory)
    monkeypatch.setattr("app.services.notification.get_postgres_db", lambda: Database())

    assert await service.unread_count("admin") == 3
