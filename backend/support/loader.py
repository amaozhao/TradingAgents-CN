"""Helpers for compatibility package facades."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import Any


def execute(
    namespace: dict[str, Any],
    facade_file: str,
    parts: Iterable[str],
    *,
    package: str,
    logical_file: str | None = None,
) -> None:
    facade_path = Path(facade_file).resolve()
    base = facade_path.parent

    namespace["__package__"] = package
    namespace["__file__"] = logical_file or str(base.with_suffix(".py"))
    source_parts: list[str] = []
    for part in parts:
        path = base / part
        text = path.read_text(encoding="utf-8")
        code = compile(text, str(path), "exec")
        if text.lstrip().startswith("SOURCE ="):
            part_namespace: dict[str, Any] = {}
            exec(code, part_namespace)
            source = part_namespace.get("SOURCE")
            if isinstance(source, str):
                source_parts.append(source)
                continue
        exec(code, namespace)

    if source_parts:
        code = compile("".join(source_parts), namespace["__file__"], "exec")
        exec(code, namespace)


def alias(name: str, module: ModuleType) -> ModuleType:
    sys.modules[name] = module
    return module
