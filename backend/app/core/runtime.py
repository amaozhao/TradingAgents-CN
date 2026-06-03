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
