from pathlib import Path

from scripts.postgres.migration.inventory.script import scan_backend


STRICT_RESPONSE_MODEL_MODULES = {
    "app/routers/akshare_init.py",
    "app/routers/analysis.py",
    "app/routers/auth_db.py",
    "app/routers/cache.py",
    "app/routers/config.py",
    "app/routers/database.py",
    "app/routers/financial_data.py",
    "app/routers/health.py",
    "app/routers/historical_data.py",
    "app/routers/logs.py",
    "app/routers/multi_period_sync.py",
    "app/routers/multi_source_sync.py",
    "app/routers/notifications.py",
    "app/routers/operation_logs.py",
    "app/routers/queue.py",
    "app/routers/reports.py",
    "app/routers/scheduler.py",
    "app/routers/screening.py",
    "app/routers/sse.py",
    "app/routers/stock_data.py",
    "app/routers/stock_sync.py",
    "app/routers/sync.py",
    "app/routers/system_config.py",
    "app/routers/usage_statistics.py",
    "app/routers/websocket_notifications.py",
}


def test_completed_router_modules_have_explicit_response_models():
    backend_root = Path(__file__).resolve().parents[1]
    inventory = scan_backend(backend_root)
    offenders = [
        item
        for item in inventory["missing_response_models"]
        if item["path"] in STRICT_RESPONSE_MODEL_MODULES
    ]

    assert offenders == []
