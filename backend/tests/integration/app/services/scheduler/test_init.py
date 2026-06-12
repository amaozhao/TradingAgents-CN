from __future__ import annotations

import importlib


def test_scheduler_service_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.scheduler")

    assert hasattr(module, "SchedulerService")
    assert hasattr(module, "TaskCancelledException")
    assert callable(module.get_utc8_now)
    assert callable(module.set_scheduler_instance)
    assert callable(module.get_scheduler_service)
    assert callable(module.update_job_progress)
