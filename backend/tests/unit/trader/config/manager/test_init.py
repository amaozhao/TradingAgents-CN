import importlib


def test_config_manager_import_facade_exports_public_api() -> None:
    module = importlib.import_module("trader.config.manager")

    assert hasattr(module, "ConfigManager")
    assert hasattr(module, "TokenTracker")
    assert hasattr(module, "CostResult")
    assert hasattr(module, "config_manager")
    assert hasattr(module, "token_tracker")
    assert module._get_project_config_dir().endswith("/config")
