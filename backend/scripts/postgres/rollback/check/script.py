from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RollbackCheck:
    name: str
    passed: bool
    detail: str


def check_rollback_evidence(
    *,
    api_smoke_json: Path | None,
    consistency_json: Path | None,
    env: Mapping[str, str | None] | None = None,
    allow_dual_write_disabled: bool = False,
    allow_inconsistent_consistency: bool = False,
    require_runtime_state_smoke: bool = True,
) -> dict[str, Any]:
    environment = env if env is not None else os.environ
    checks: list[RollbackCheck] = []

    read_value = environment.get("POSTGRES_READ_ENABLED")
    read_disabled = _is_false(read_value)
    checks.append(
        RollbackCheck(
            "postgres_read_disabled",
            read_disabled,
            f"POSTGRES_READ_ENABLED={_display_value(read_value)}",
        )
    )

    dual_write_value = environment.get("POSTGRES_DUAL_WRITE_ENABLED")
    dual_write_enabled = _is_true(dual_write_value)
    dual_write_disabled = _is_false(dual_write_value)
    if dual_write_enabled:
        checks.append(
            RollbackCheck(
                "dual_write_state_recorded",
                True,
                f"POSTGRES_DUAL_WRITE_ENABLED={_display_value(dual_write_value)}",
            )
        )
    elif dual_write_disabled and allow_dual_write_disabled:
        checks.append(
            RollbackCheck(
                "dual_write_state_recorded",
                True,
                "dual-write disabled with explicit replay follow-up required",
            )
        )
    else:
        checks.append(
            RollbackCheck(
                "dual_write_state_recorded",
                False,
                f"POSTGRES_DUAL_WRITE_ENABLED={_display_value(dual_write_value)}",
            )
        )

    checks.extend(
        _check_api_smoke_file(
            api_smoke_json, require_runtime_state_smoke=require_runtime_state_smoke
        )
    )

    consistency_checks = _check_consistency_file(consistency_json)
    if allow_inconsistent_consistency:
        consistency_checks = [
            RollbackCheck(
                check.name,
                True if check.name == "consistency_all_consistent" else check.passed,
                f"{check.detail}; diagnostic inconsistency allowed after rollback",
            )
            for check in consistency_checks
        ]
    checks.extend(consistency_checks)

    return {
        "all_passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def write_rollback_target_manifest(
    *,
    output_dir: Path,
    target_env: str | None = None,
    env: Mapping[str, str | None] | None = None,
    api_smoke_json: Path | None = None,
    consistency_json: Path | None = None,
) -> Path:
    environment = env if env is not None else os.environ
    effective_target_env = target_env or environment.get("TRADING_AGENTS_TARGET_ENV")
    if not effective_target_env:
        raise ValueError(
            "missing target environment: provide --target-env or TRADING_AGENTS_TARGET_ENV"
        )
    manifest = {
        "schema_version": "1",
        "created_at": datetime.now(UTC).isoformat(),
        "target_env": effective_target_env,
        "target_phase": "rollback",
        "include_api_smoke": api_smoke_json is not None,
        "runtime_log_included": False,
        "require_explicit_env": True,
        "postgres_read_enabled": environment.get("POSTGRES_READ_ENABLED"),
        "postgres_dual_write_enabled": environment.get("POSTGRES_DUAL_WRITE_ENABLED"),
        "expected_postgres_read_enabled": environment.get(
            "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED"
        ),
        "expected_postgres_dual_write_enabled": environment.get(
            "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED"
        ),
        "api_smoke_json": str(api_smoke_json) if api_smoke_json else None,
        "consistency_json": str(consistency_json) if consistency_json else None,
        "git_commit": environment.get("GIT_COMMIT")
        or environment.get("SOURCE_VERSION"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "00_target_manifest.json"
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def _check_api_smoke_file(
    path: Path | None, *, require_runtime_state_smoke: bool
) -> list[RollbackCheck]:
    if path is None:
        return [RollbackCheck("api_smoke_present", False, "missing path")]
    if not path.exists():
        return [RollbackCheck("api_smoke_present", False, f"missing {path}")]
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return [
            RollbackCheck("api_smoke_present", True, str(path)),
            RollbackCheck("api_smoke_all_passed", False, str(exc)),
        ]
    checks = [
        RollbackCheck("api_smoke_present", True, str(path)),
        RollbackCheck(
            "api_smoke_all_passed",
            payload.get("all_passed") is True,
            f"all_passed={payload.get('all_passed')}",
        ),
    ]
    if require_runtime_state_smoke:
        checks.append(_check_migration_state_smoke(payload))
    return checks


def _check_migration_state_smoke(payload: dict[str, Any]) -> RollbackCheck:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return RollbackCheck(
            "api_smoke_migration_state", False, "api_smoke checks is not a list"
        )
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != "migration_state":
            continue
        return RollbackCheck(
            "api_smoke_migration_state",
            check.get("status") == "passed",
            f"status={check.get('status')}, detail={check.get('detail')}",
        )
    return RollbackCheck(
        "api_smoke_migration_state", False, "missing migration_state check"
    )


def _check_consistency_file(path: Path | None) -> list[RollbackCheck]:
    if path is None:
        return [RollbackCheck("consistency_present", False, "missing path")]
    if not path.exists():
        return [RollbackCheck("consistency_present", False, f"missing {path}")]
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return [
            RollbackCheck("consistency_present", True, str(path)),
            RollbackCheck("consistency_all_consistent", False, str(exc)),
        ]
    return [
        RollbackCheck("consistency_present", True, str(path)),
        RollbackCheck(
            "consistency_all_consistent",
            payload.get("all_consistent") is True,
            f"all_consistent={payload.get('all_consistent')}",
        ),
    ]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _is_false(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower() in FALSE_VALUES


def _is_true(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower() in TRUE_VALUES


def _display_value(value: str | None) -> str:
    return "<unset>" if value is None else value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate PostgreSQL cutover rollback evidence."
    )
    parser.add_argument("--api-smoke-json", type=Path, required=True)
    parser.add_argument("--consistency-json", type=Path, required=True)
    parser.add_argument("--allow-dual-write-disabled", action="store_true")
    parser.add_argument("--allow-inconsistent-consistency", action="store_true")
    parser.add_argument("--no-require-runtime-state-smoke", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional rollback evidence directory where 00_target_manifest.json will be written.",
    )
    parser.add_argument(
        "--target-env",
        help="Non-secret target environment label for the generated rollback manifest.",
    )
    args = parser.parse_args()

    if args.output_dir:
        try:
            write_rollback_target_manifest(
                output_dir=args.output_dir,
                target_env=args.target_env,
                api_smoke_json=args.api_smoke_json,
                consistency_json=args.consistency_json,
            )
        except ValueError as exc:
            result = {
                "all_passed": False,
                "checks": [
                    {
                        "name": "target_manifest_env",
                        "passed": False,
                        "detail": str(exc),
                    }
                ],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            raise SystemExit(1) from exc

    result = check_rollback_evidence(
        api_smoke_json=args.api_smoke_json,
        consistency_json=args.consistency_json,
        allow_dual_write_disabled=args.allow_dual_write_disabled,
        allow_inconsistent_consistency=args.allow_inconsistent_consistency,
        require_runtime_state_smoke=not args.no_require_runtime_state_smoke,
    )
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "rollback_check.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
