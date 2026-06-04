from __future__ import annotations

import importlib


def test_analysis_service_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.analysis.service")

    assert hasattr(module, "AnalysisService")
    assert callable(module.get_analysis_service)

    for method_name in (
        "submit_single_analysis",
        "submit_batch_analysis",
        "execute_analysis_task",
        "get_task_status",
        "cancel_task",
    ):
        assert hasattr(module.AnalysisService, method_name)
