from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


STARTUP_SYNC_DISABLED_PATTERN = "SYNC_STOCK_BASICS_ENABLED=false"
DUAL_WRITE_PATTERN = re.compile(r"PostgreSQL dual-write .*collection=(?P<collection>\S+) .*status=(?P<status>\S+)")
DUAL_WRITE_FAILED_PATTERN = re.compile(r"PostgreSQL dual-write .*status=failed")
MONGO_ONLY_PATTERN = "Mongo-only write retained during PostgreSQL migration"


@dataclass(frozen=True)
class LogCheck:
    name: str
    passed: bool
    detail: str


def check_runtime_log(
    log_path: Path,
    *,
    require_startup_gate: bool = True,
    require_dual_write: bool = True,
    allow_dual_write_failures: bool = False,
    allow_mongo_only: bool = False,
) -> dict[str, Any]:
    checks: list[LogCheck] = []
    if not log_path.exists():
        checks.append(LogCheck("log_exists", False, f"missing {log_path}"))
        return _result(log_path, checks)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    checks.append(LogCheck("log_exists", True, str(log_path)))

    startup_disabled_count = text.count(STARTUP_SYNC_DISABLED_PATTERN)
    if require_startup_gate:
        checks.append(
            LogCheck(
                "startup_stock_basics_disabled",
                startup_disabled_count > 0,
                f"matches={startup_disabled_count}",
            )
        )
    else:
        checks.append(
            LogCheck(
                "startup_stock_basics_disabled",
                True,
                f"not_required matches={startup_disabled_count}",
            )
        )

    dual_write_events = list(DUAL_WRITE_PATTERN.finditer(text))
    dual_write_written = [match for match in dual_write_events if match.group("status") == "written"]
    if require_dual_write:
        checks.append(
            LogCheck(
                "dual_write_written_event",
                len(dual_write_written) > 0,
                f"written={len(dual_write_written)} total={len(dual_write_events)} collections={_format_collections(dual_write_written)}",
            )
        )
    else:
        checks.append(
            LogCheck(
                "dual_write_written_event",
                True,
                f"not_required written={len(dual_write_written)} total={len(dual_write_events)}",
            )
        )

    failed_count = len(DUAL_WRITE_FAILED_PATTERN.findall(text))
    checks.append(
        LogCheck(
            "dual_write_failures_absent",
            allow_dual_write_failures or failed_count == 0,
            f"failures={failed_count}",
        )
    )

    mongo_only_count = text.count(MONGO_ONLY_PATTERN)
    checks.append(
        LogCheck(
            "mongo_only_writes_absent",
            allow_mongo_only or mongo_only_count == 0,
            f"mongo_only_warnings={mongo_only_count}",
        )
    )

    return _result(log_path, checks)


def _format_collections(matches) -> str:
    collections = [match.group("collection") for match in matches]
    unique_collections = list(dict.fromkeys(collections))
    if not unique_collections:
        return "none"
    visible = unique_collections[:10]
    suffix = "" if len(unique_collections) <= 10 else f"...(+{len(unique_collections) - 10})"
    return ",".join(visible) + suffix


def _result(log_path: Path, checks: list[LogCheck]) -> dict[str, Any]:
    return {
        "log_path": str(log_path),
        "all_passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PostgreSQL migration runtime log evidence.")
    parser.add_argument("log_path", type=Path)
    parser.add_argument("--no-require-startup-gate", action="store_true")
    parser.add_argument("--no-require-dual-write", action="store_true")
    parser.add_argument("--allow-dual-write-failures", action="store_true")
    parser.add_argument("--allow-mongo-only", action="store_true")
    args = parser.parse_args()

    result = check_runtime_log(
        args.log_path,
        require_startup_gate=not args.no_require_startup_gate,
        require_dual_write=not args.no_require_dual_write,
        allow_dual_write_failures=args.allow_dual_write_failures,
        allow_mongo_only=args.allow_mongo_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
