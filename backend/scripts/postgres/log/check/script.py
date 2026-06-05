from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeLogCheck:
    name: str
    passed: bool
    detail: str


def check_runtime_log(
    runtime_log: Path,
    *,
    require_startup_gate: bool = True,
    require_dual_write: bool = True,
    allow_dual_write_failures: bool = False,
) -> dict[str, Any]:
    text = runtime_log.read_text(encoding="utf-8")
    checks: list[RuntimeLogCheck] = []

    if require_startup_gate:
        startup_seen = "SYNC_STOCK_BASICS_ENABLED=false" in text
        checks.append(
            RuntimeLogCheck(
                "startup_sync_disabled",
                startup_seen,
                "found startup sync disabled log" if startup_seen else "missing SYNC_STOCK_BASICS_ENABLED=false log",
            )
        )

    dual_write_written = "PostgreSQL dual-write" in text and "status=written" in text
    dual_write_failed = "PostgreSQL dual-write" in text and "status=failed" in text
    if require_dual_write:
        checks.append(
            RuntimeLogCheck(
                "postgres_dual_write_seen",
                dual_write_written or (allow_dual_write_failures and dual_write_failed),
                _dual_write_detail(
                    written=dual_write_written,
                    failed=dual_write_failed,
                    allow_failures=allow_dual_write_failures,
                ),
            )
        )

    return {
        "all_passed": all(check.passed for check in checks),
        "runtime_log": str(runtime_log),
        "checks": [asdict(check) for check in checks],
    }


def _dual_write_detail(*, written: bool, failed: bool, allow_failures: bool) -> str:
    if written:
        return "found status=written dual-write log"
    if failed and allow_failures:
        return "found allowed status=failed dual-write log"
    if failed:
        return "found status=failed dual-write log"
    return "missing PostgreSQL dual-write status=written log"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PostgreSQL migration runtime log evidence.")
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--no-require-startup-gate", action="store_true")
    parser.add_argument("--no-require-dual-write", action="store_true")
    parser.add_argument("--allow-dual-write-failures", action="store_true")
    args = parser.parse_args()

    result = check_runtime_log(
        args.runtime_log,
        require_startup_gate=not args.no_require_startup_gate,
        require_dual_write=not args.no_require_dual_write,
        allow_dual_write_failures=args.allow_dual_write_failures,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
