"""Helpers for registering migrated historical test modules."""

from __future__ import annotations

import re
from importlib import import_module
from typing import Any

import pytest


def _test_name(module_name: str) -> str:
    token = re.sub(r"\W+", "_", module_name).strip("_")
    return f"test_{token}_migratedmodule"


def export_module(namespace: dict[str, Any], module_name: str) -> None:
    @pytest.mark.integration
    def migrated_module_import_smoke() -> None:
        import_module(module_name)

    migrated_module_import_smoke.__name__ = _test_name(module_name)
    namespace[migrated_module_import_smoke.__name__] = migrated_module_import_smoke
