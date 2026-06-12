from support.registry import export_module as _export_module
import importlib

_export_module(globals(), "support.debug.deepseek.cost.module")
_export_module(globals(), "support.config.loading.module")
_export_module(globals(), "support.config.management.module")
_export_module(globals(), "support.deepseek.cost.fi.module")
_export_module(globals(), "support.config.loading.module")
_export_module(globals(), "support.file.loading.debug.module")
del _export_module


def test_config_manager_import_facade_exports_public_api() -> None:
    module = importlib.import_module("trader.config.manager")

    assert hasattr(module, "ConfigManager")
    assert hasattr(module, "TokenTracker")
    assert hasattr(module, "CostResult")
    assert hasattr(module, "config_manager")
    assert hasattr(module, "token_tracker")
    assert module._get_project_config_dir().endswith("/config")
