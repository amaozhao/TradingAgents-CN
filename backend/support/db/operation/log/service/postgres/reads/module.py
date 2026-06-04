import pytest

from app.core.config import settings
from app.models.operations import (
    OperationLogQuery,
    OperationLogResponse,
    OperationLogStats,
)
from app.services.operation import OperationLogService


@pytest.mark.asyncio
async def test_get_logs_uses_postgres_when_enabled(monkeypatch):
    service = OperationLogService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg(query):
        assert query.action_type == "user_login"
        return (
            [
                OperationLogResponse(
                    id="log-1",
                    user_id="user-1",
                    username="admin",
                    action_type="user_login",
                    action="用户登录",
                    success=True,
                    timestamp="2026-06-03T10:00:00",
                    created_at="2026-06-03T10:00:00",
                )
            ],
            1,
        )

    monkeypatch.setattr(service, "_get_logs_from_postgres", fake_pg)

    logs, total = await service.get_logs(OperationLogQuery(action_type="user_login"))

    assert total == 1
    assert logs[0].id == "log-1"
    assert logs[0].user_id == "user-1"
    assert logs[0].action_type == "user_login"


@pytest.mark.asyncio
async def test_get_stats_uses_postgres_when_enabled(monkeypatch):
    service = OperationLogService()
    monkeypatch.setattr(settings, "POSTGRES_READ_ENABLED", True)

    async def fake_pg_stats(days):
        assert days == 7
        return OperationLogStats(
            total_logs=3,
            success_logs=2,
            failed_logs=1,
            success_rate=66.67,
            action_type_distribution={"user_login": 3},
            hourly_distribution=[{"hour": "10:00", "count": 3}],
        )

    monkeypatch.setattr(service, "_get_stats_from_postgres", fake_pg_stats)

    stats = await service.get_stats(days=7)

    assert stats.total_logs == 3
    assert stats.success_logs == 2
    assert stats.action_type_distribution == {"user_login": 3}
