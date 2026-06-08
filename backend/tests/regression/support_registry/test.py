from __future__ import annotations

from support.registry import export_module


def test_export_module_skips_missing_support_modules():
    namespace: dict[str, object] = {}

    export_module(namespace, "support.this.module.does.not.exist")

    assert namespace == {}
