from __future__ import annotations

import importlib


def test_config_service_import_facade_exports_public_api() -> None:
    module = importlib.import_module("app.services.config")

    assert hasattr(module, "ConfigService")
    assert isinstance(module.config_service, module.ConfigService)

    service = module.ConfigService()
    for method_name in (
        "get_system_config",
        "save_system_config",
        "get_llm_providers",
        "test_llm_config",
        "test_data_source_config",
        "get_model_catalog",
        "get_database_configs",
    ):
        assert hasattr(service, method_name)
