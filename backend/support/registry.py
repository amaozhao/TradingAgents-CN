"""Helpers for registering migrated historical test modules."""

from __future__ import annotations

import re
from importlib.util import find_spec
from importlib import import_module
from typing import Any

import pytest


def _test_name(module_name: str) -> str:
    token = re.sub(r"\W+", "_", module_name).strip("_")
    return f"test_{token}_migratedmodule"


def export_module(namespace: dict[str, Any], module_name: str) -> None:
    try:
        module_spec = find_spec(module_name)
    except ModuleNotFoundError:
        return
    if module_spec is None:
        return

    @pytest.mark.integration
    def migrated_module_import_smoke() -> None:
        import_module(module_name)

    migrated_module_import_smoke.__name__ = _test_name(module_name)
    namespace[migrated_module_import_smoke.__name__] = migrated_module_import_smoke
