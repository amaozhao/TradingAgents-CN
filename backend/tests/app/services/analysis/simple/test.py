from __future__ import annotations

import importlib


def test_simple_analysis_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.analysis.simple")

    assert hasattr(module, "SimpleAnalysisService")
    assert callable(module.get_simple_analysis_service)

    service = module.SimpleAnalysisService()
    for method_name in (
        "create_analysis_task",
        "execute_analysis_background",
        "get_task_status",
        "list_user_tasks",
        "cleanup_zombie_tasks",
    ):
        assert hasattr(service, method_name)

    for helper_name in (
        "create_analysis_config",
        "get_provider_by_model_name",
        "get_provider_by_model_name_sync",
        "get_provider_and_url_by_model_sync",
    ):
        assert hasattr(module, helper_name)
