from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping


def apply_runtime_env(
    values: Mapping[str, str | None],
    *,
    environ: MutableMapping[str, str] | None = None,
    overwrite: bool = True,
) -> dict[str, str]:
    """Apply runtime env values through one auditable boundary."""

    target = os.environ if environ is None else environ
    applied: dict[str, str] = {}

    for key, value in values.items():
        if value is None or value == "":
            continue
        if not overwrite and key in target:
            continue
        string_value = str(value)
        target[key] = string_value
        applied[key] = string_value

    return applied


def clear_runtime_env(
    keys: list[str] | tuple[str, ...],
    *,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Remove runtime env values through the same auditable boundary."""

    target = os.environ if environ is None else environ
    for key in keys:
        target.pop(key, None)


def runtime_env_snapshot(
    *,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a copy of the runtime environment through the audited boundary."""

    target = os.environ if environ is None else environ
    return dict(target)
