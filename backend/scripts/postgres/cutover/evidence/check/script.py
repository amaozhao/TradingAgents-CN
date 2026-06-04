from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REQUIRED_STEPS = [
    "inventory",
    "alembic_offline_sql",
    "consistency",
    "query_plan",
    "data_path_smoke",
]


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    passed: bool
    detail: str


def check_evidence_bundle(
    output_dir: Path,
    *,
    require_api_smoke: bool = False,
    require_api_migration_state: bool = False,
    require_runtime_log_check: bool = False,
    require_rollback_check: bool = False,
    require_target_manifest: bool = False,
    expected_phase: str | None = None,
    rollback_only: bool = False,
) -> dict[str, Any]:
    checks: list[EvidenceCheck] = []

    if require_target_manifest or expected_phase is not None:
        checks.extend(
            _check_target_manifest_file(output_dir, expected_phase=expected_phase)
        )

    if rollback_only:
        checks.extend(_check_rollback_check_file(output_dir))
        return _result(output_dir, checks)

    summary_path = output_dir / "summary.json"
    summary: dict[str, Any] | None = None

    if not summary_path.exists():
        checks.append(EvidenceCheck("summary_exists", False, f"missing {summary_path}"))
    else:
        try:
            summary = _load_json(summary_path)
            checks.append(
                EvidenceCheck(
                    "summary_exists", True, "summary.json exists and is valid JSON"
                )
            )
        except ValueError as exc:
            checks.append(EvidenceCheck("summary_exists", False, str(exc)))

    if summary is None:
        return _result(output_dir, checks)

    checks.append(
        EvidenceCheck(
            "summary_all_passed",
            summary.get("all_passed") is True,
            f"all_passed={summary.get('all_passed')}",
        )
    )
    checks.append(
        EvidenceCheck(
            "summary_not_dry_run",
            summary.get("dry_run") is False,
            f"dry_run={summary.get('dry_run')}",
        )
    )

    results = summary.get("results")
    if not isinstance(results, list):
        checks.append(
            EvidenceCheck("results_list", False, "summary.results is not a list")
        )
        return _result(output_dir, checks)
    checks.append(EvidenceCheck("results_list", True, f"results={len(results)}"))

    result_by_name = {
        item.get("name"): item
        for item in results
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    required_steps = [*REQUIRED_STEPS]
    if require_api_smoke or require_api_migration_state:
        required_steps.append("api_smoke")

    for step_name in required_steps:
        result = result_by_name.get(step_name)
        if result is None:
            checks.append(
                EvidenceCheck(f"{step_name}_present", False, "missing step result")
            )
            continue
        checks.append(
            EvidenceCheck(f"{step_name}_present", True, "step result present")
        )
        checks.append(
            EvidenceCheck(
                f"{step_name}_passed",
                result.get("status") == "passed",
                f"status={result.get('status')}",
            )
        )
        output_file = result.get("output_file")
        if not isinstance(output_file, str) or not output_file:
            checks.append(
                EvidenceCheck(f"{step_name}_output_file", False, "missing output_file")
            )
            continue
        output_path = Path(output_file)
        if not output_path.exists():
            checks.append(
                EvidenceCheck(
                    f"{step_name}_output_file", False, f"missing {output_path}"
                )
            )
            continue
        checks.append(EvidenceCheck(f"{step_name}_output_file", True, str(output_path)))
        checks.extend(_semantic_checks(step_name, output_path))
        if step_name == "api_smoke" and require_api_migration_state:
            checks.append(_check_api_migration_state(output_path))

    if not require_api_smoke and "api_smoke" in result_by_name:
        result = result_by_name["api_smoke"]
        checks.append(
            EvidenceCheck(
                "api_smoke_if_present_passed",
                result.get("status") == "passed",
                f"status={result.get('status')}",
            )
        )

    if require_runtime_log_check:
        result = result_by_name.get("runtime_log_check")
        if result is None:
            checks.extend(_check_runtime_log_check_file(output_dir))
        else:
            checks.append(
                EvidenceCheck("runtime_log_check_present", True, "step result present")
            )
            checks.append(
                EvidenceCheck(
                    "runtime_log_check_passed",
                    result.get("status") == "passed",
                    f"status={result.get('status')}",
                )
            )
            output_file = result.get("output_file")
            if not isinstance(output_file, str) or not output_file:
                checks.append(
                    EvidenceCheck(
                        "runtime_log_check_output_file", False, "missing output_file"
                    )
                )
            else:
                output_path = Path(output_file)
                if output_path.exists():
                    checks.append(
                        EvidenceCheck(
                            "runtime_log_check_output_file", True, str(output_path)
                        )
                    )
                    checks.extend(_semantic_checks("runtime_log_check", output_path))
                else:
                    checks.append(
                        EvidenceCheck(
                            "runtime_log_check_output_file",
                            False,
                            f"missing {output_path}",
                        )
                    )

    if require_rollback_check:
        result = result_by_name.get("rollback_check")
        if result is None:
            checks.extend(_check_rollback_check_file(output_dir))
        else:
            checks.append(
                EvidenceCheck("rollback_check_present", True, "step result present")
            )
            checks.append(
                EvidenceCheck(
                    "rollback_check_passed",
                    result.get("status") == "passed",
                    f"status={result.get('status')}",
                )
            )
            output_file = result.get("output_file")
            if not isinstance(output_file, str) or not output_file:
                checks.append(
                    EvidenceCheck(
                        "rollback_check_output_file", False, "missing output_file"
                    )
                )
            else:
                output_path = Path(output_file)
                if output_path.exists():
                    checks.append(
                        EvidenceCheck(
                            "rollback_check_output_file", True, str(output_path)
                        )
                    )
                    checks.extend(_semantic_checks("rollback_check", output_path))
                else:
                    checks.append(
                        EvidenceCheck(
                            "rollback_check_output_file",
                            False,
                            f"missing {output_path}",
                        )
                    )

    return _result(output_dir, checks)


def _semantic_checks(step_name: str, output_path: Path) -> list[EvidenceCheck]:
    validators: dict[str, Callable[[Path], EvidenceCheck]] = {
        "inventory": _check_inventory,
        "alembic_offline_sql": _check_offline_sql,
        "consistency": _check_consistency,
        "query_plan": _check_query_plan,
        "data_path_smoke": lambda path: _check_all_passed_json(path, "data_path_smoke"),
        "api_smoke": lambda path: _check_all_passed_json(path, "api_smoke"),
        "runtime_log_check": lambda path: _check_all_passed_json(
            path, "runtime_log_check"
        ),
        "rollback_check": lambda path: _check_all_passed_json(path, "rollback_check"),
    }
    validator = validators.get(step_name)
    if validator is None:
        return []
    return [validator(output_path)]


def _check_inventory(path: Path) -> EvidenceCheck:
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return EvidenceCheck("inventory_semantic", False, str(exc))
    summary = (
        payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    )
    ok = (
        summary.get("response_model_dict_endpoints") == 0
        and summary.get("raw_dict_request_bodies") == 0
    )
    return EvidenceCheck(
        "inventory_semantic",
        ok,
        f"response_model_dict_endpoints={summary.get('response_model_dict_endpoints')}, raw_dict_request_bodies={summary.get('raw_dict_request_bodies')}",
    )


def _check_offline_sql(path: Path) -> EvidenceCheck:
    size = path.stat().st_size
    return EvidenceCheck("alembic_offline_sql_semantic", size > 0, f"bytes={size}")


def _check_consistency(path: Path) -> EvidenceCheck:
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return EvidenceCheck("consistency_semantic", False, str(exc))
    return EvidenceCheck(
        "consistency_semantic",
        payload.get("all_consistent") is True,
        f"all_consistent={payload.get('all_consistent')}",
    )


def _check_query_plan(path: Path) -> EvidenceCheck:
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return EvidenceCheck("query_plan_semantic", False, str(exc))
    return EvidenceCheck(
        "query_plan_semantic",
        payload.get("all_required_without_payload_filter") is True,
        f"all_required_without_payload_filter={payload.get('all_required_without_payload_filter')}",
    )


def _check_all_passed_json(path: Path, name: str) -> EvidenceCheck:
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return EvidenceCheck(f"{name}_semantic", False, str(exc))
    return EvidenceCheck(
        f"{name}_semantic",
        payload.get("all_passed") is True,
        f"all_passed={payload.get('all_passed')}",
    )


def _check_api_migration_state(path: Path) -> EvidenceCheck:
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return EvidenceCheck("api_smoke_migration_state", False, str(exc))
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return EvidenceCheck(
            "api_smoke_migration_state", False, "api_smoke checks is not a list"
        )
    for check in checks:
        if isinstance(check, dict) and check.get("name") == "migration_state":
            return EvidenceCheck(
                "api_smoke_migration_state",
                check.get("status") == "passed",
                f"status={check.get('status')}, detail={check.get('detail')}",
            )
    return EvidenceCheck(
        "api_smoke_migration_state", False, "missing migration_state check"
    )


def _check_runtime_log_check_file(output_dir: Path) -> list[EvidenceCheck]:
    path = output_dir / "runtime_log_check.json"
    if not path.exists():
        return [EvidenceCheck("runtime_log_check_present", False, f"missing {path}")]
    checks = [EvidenceCheck("runtime_log_check_present", True, str(path))]
    try:
        payload = _load_json(path)
    except ValueError as exc:
        checks.append(EvidenceCheck("runtime_log_check_semantic", False, str(exc)))
        return checks
    checks.append(
        EvidenceCheck(
            "runtime_log_check_semantic",
            payload.get("all_passed") is True,
            f"all_passed={payload.get('all_passed')}",
        )
    )
    return checks


def _check_rollback_check_file(output_dir: Path) -> list[EvidenceCheck]:
    path = output_dir / "rollback_check.json"
    if not path.exists():
        return [EvidenceCheck("rollback_check_present", False, f"missing {path}")]
    checks = [EvidenceCheck("rollback_check_present", True, str(path))]
    checks.extend(_semantic_checks("rollback_check", path))
    return checks


def _check_target_manifest_file(
    output_dir: Path, *, expected_phase: str | None
) -> list[EvidenceCheck]:
    path = output_dir / "00_target_manifest.json"
    if not path.exists():
        return [EvidenceCheck("target_manifest_present", False, f"missing {path}")]
    checks = [EvidenceCheck("target_manifest_present", True, str(path))]
    try:
        payload = _load_json(path)
    except ValueError as exc:
        checks.append(EvidenceCheck("target_manifest_json", False, str(exc)))
        return checks
    checks.append(EvidenceCheck("target_manifest_json", True, "valid JSON object"))

    target_env = payload.get("target_env")
    checks.append(
        EvidenceCheck(
            "target_manifest_env",
            isinstance(target_env, str) and bool(target_env.strip()),
            f"target_env={target_env!r}",
        )
    )

    phase = payload.get("target_phase")
    allowed_phases = {"pre-read", "post-read", "rollback"}
    checks.append(
        EvidenceCheck(
            "target_manifest_phase",
            phase in allowed_phases,
            f"target_phase={phase!r}",
        )
    )
    if expected_phase is not None:
        checks.append(
            EvidenceCheck(
                "target_manifest_expected_phase",
                phase == expected_phase,
                f"target_phase={phase!r}, expected_phase={expected_phase!r}",
            )
        )

    checks.append(
        EvidenceCheck(
            "target_manifest_created_at",
            isinstance(payload.get("created_at"), str)
            and bool(payload.get("created_at")),
            f"created_at={payload.get('created_at')!r}",
        )
    )
    return checks


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _result(output_dir: Path, checks: list[EvidenceCheck]) -> dict[str, Any]:
    return {
        "output_dir": str(output_dir),
        "all_passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a saved PostgreSQL cutover evidence bundle."
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--require-api-smoke", action="store_true")
    parser.add_argument("--require-api-migration-state", action="store_true")
    parser.add_argument("--require-runtime-log-check", action="store_true")
    parser.add_argument("--require-rollback-check", action="store_true")
    parser.add_argument("--require-target-manifest", action="store_true")
    parser.add_argument(
        "--expected-phase", choices=["pre-read", "post-read", "rollback"]
    )
    parser.add_argument("--rollback-only", action="store_true")
    args = parser.parse_args()

    result = check_evidence_bundle(
        args.output_dir,
        require_api_smoke=args.require_api_smoke,
        require_api_migration_state=args.require_api_migration_state,
        require_runtime_log_check=args.require_runtime_log_check,
        require_rollback_check=args.require_rollback_check,
        require_target_manifest=args.require_target_manifest,
        expected_phase=args.expected_phase,
        rollback_only=args.rollback_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
