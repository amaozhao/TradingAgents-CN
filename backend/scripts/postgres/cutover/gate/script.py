from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_OUTPUT_ROOT = Path("/tmp/trading_agents_postgres_cutover_evidence")


@dataclass(frozen=True)
class GateStep:
    name: str
    command: list[str]
    output_file: str
    cwd: Path = REPO_ROOT


@dataclass
class GateResult:
    name: str
    command: list[str]
    cwd: str
    output_file: str
    returncode: int | None
    status: str
    detail: str = ""


def build_gate_steps(
    *,
    sample_limit: int,
    compile_only_query_plan: bool,
    include_api_smoke: bool,
    runtime_log: Path | None = None,
    require_runtime_startup_gate: bool = True,
    require_runtime_dual_write: bool = True,
    allow_runtime_dual_write_failures: bool = False,
) -> list[GateStep]:
    python = sys.executable
    query_plan_command = [python, "backend/scripts/postgres/query/plan/check/script.py"]
    if compile_only_query_plan:
        query_plan_command.append("--compile-only")
    runtime_log_command = [
        python,
        "backend/scripts/postgres/log/check/script.py",
    ]
    if runtime_log is not None:
        runtime_log_command.append(str(runtime_log))
        if not require_runtime_startup_gate:
            runtime_log_command.append("--no-require-startup-gate")
        if not require_runtime_dual_write:
            runtime_log_command.append("--no-require-dual-write")
        if allow_runtime_dual_write_failures:
            runtime_log_command.append("--allow-dual-write-failures")

    steps = [
        GateStep(
            name="inventory",
            command=[python, "backend/scripts/postgres/migration/inventory/script.py"],
            output_file="01_inventory.json",
        ),
        GateStep(
            name="alembic_offline_sql",
            command=["alembic", "-c", "alembic.ini", "upgrade", "head", "--sql"],
            output_file="02_alembic_offline.sql",
            cwd=BACKEND_ROOT,
        ),
        GateStep(
            name="consistency",
            command=[
                python,
                "backend/scripts/postgres/consistency/check/script.py",
                "--sample-limit",
                str(sample_limit),
            ],
            output_file="03_consistency.json",
        ),
        GateStep(
            name="query_plan",
            command=query_plan_command,
            output_file="04_query_plan.json",
        ),
        GateStep(
            name="data_path_smoke",
            command=[
                python,
                "backend/scripts/postgres/cutover/smoke/script.py",
                "--pretty",
            ],
            output_file="05_data_path_smoke.json",
        ),
    ]
    if include_api_smoke:
        steps.append(
            GateStep(
                name="api_smoke",
                command=[
                    python,
                    "backend/scripts/postgres/api/smoke/script.py",
                    "--pretty",
                ],
                output_file="06_api_smoke.json",
            )
        )
    if runtime_log is not None:
        steps.append(
            GateStep(
                name="runtime_log_check",
                command=runtime_log_command,
                output_file="runtime_log_check.json",
            )
        )
    return steps


def run_gate(
    *,
    output_dir: Path,
    sample_limit: int,
    compile_only_query_plan: bool,
    include_api_smoke: bool,
    runtime_log: Path | None = None,
    require_runtime_startup_gate: bool = True,
    require_runtime_dual_write: bool = True,
    allow_runtime_dual_write_failures: bool = False,
    dry_run: bool,
    require_explicit_env: bool = False,
    target_env: str | None = None,
    target_phase: str | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    steps = build_gate_steps(
        sample_limit=sample_limit,
        compile_only_query_plan=compile_only_query_plan,
        include_api_smoke=include_api_smoke,
        runtime_log=runtime_log,
        require_runtime_startup_gate=require_runtime_startup_gate,
        require_runtime_dual_write=require_runtime_dual_write,
        allow_runtime_dual_write_failures=allow_runtime_dual_write_failures,
    )
    results: list[GateResult] = []

    if require_explicit_env:
        status, detail = _validate_explicit_target_environment(
            include_api_smoke=include_api_smoke,
            target_env=target_env,
            target_phase=target_phase,
        )
        results.append(
            GateResult(
                name="target_env_preflight",
                command=[],
                cwd=str(REPO_ROOT),
                output_file=str(output_dir / "00_target_env_preflight.json"),
                returncode=None,
                status="dry_run" if dry_run else status,
                detail="command not executed" if dry_run else detail,
            )
        )
        (output_dir / "00_target_env_preflight.json").write_text(
            json.dumps(
                {"status": results[-1].status, "detail": results[-1].detail},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if not dry_run and status == "failed":
            summary = _build_summary(
                output_dir=output_dir, dry_run=dry_run, results=results
            )
            (output_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return summary

    manifest = _build_target_manifest(
        output_dir=output_dir,
        target_env=target_env,
        target_phase=target_phase,
        include_api_smoke=include_api_smoke,
        runtime_log=runtime_log,
        require_explicit_env=require_explicit_env,
    )
    if manifest.get("target_env") and manifest.get("target_phase"):
        (output_dir / "00_target_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    for step in steps:
        output_file = output_dir / step.output_file
        if dry_run:
            results.append(
                GateResult(
                    name=step.name,
                    command=step.command,
                    cwd=str(step.cwd),
                    output_file=str(output_file),
                    returncode=None,
                    status="dry_run",
                    detail="command not executed",
                )
            )
            continue

        with output_file.open("w", encoding="utf-8") as handle:
            process = subprocess.run(
                step.command,
                cwd=step.cwd,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        status, detail = _evaluate_step_output(step, output_file, process.returncode)
        results.append(
            GateResult(
                name=step.name,
                command=step.command,
                cwd=str(step.cwd),
                output_file=str(output_file),
                returncode=process.returncode,
                status=status,
                detail=detail,
            )
        )
        if status == "failed":
            break

    summary = _build_summary(output_dir=output_dir, dry_run=dry_run, results=results)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _build_summary(
    *, output_dir: Path, dry_run: bool, results: list[GateResult]
) -> dict:
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "output_dir": str(output_dir),
        "all_passed": all(result.status in {"passed", "dry_run"} for result in results),
        "environment": _safe_environment_snapshot(),
        "results": [asdict(result) for result in results],
    }


def _build_target_manifest(
    *,
    output_dir: Path,
    target_env: str | None,
    target_phase: str | None,
    include_api_smoke: bool,
    runtime_log: Path | None,
    require_explicit_env: bool,
) -> dict[str, str | bool | None]:
    return {
        "schema_version": "1",
        "created_at": datetime.now(UTC).isoformat(),
        "target_env": target_env or os.getenv("TRADING_AGENTS_TARGET_ENV"),
        "target_phase": target_phase or os.getenv("TRADING_AGENTS_CUTOVER_PHASE"),
        "output_dir": str(output_dir),
        "include_api_smoke": include_api_smoke,
        "runtime_log_included": runtime_log is not None,
        "require_explicit_env": require_explicit_env,
        "postgres_read_enabled": os.getenv("POSTGRES_READ_ENABLED"),
        "postgres_dual_write_enabled": os.getenv("POSTGRES_DUAL_WRITE_ENABLED"),
        "expected_postgres_read_enabled": os.getenv(
            "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED"
        ),
        "expected_postgres_dual_write_enabled": os.getenv(
            "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED"
        ),
        "sync_stock_basics_enabled": os.getenv("SYNC_STOCK_BASICS_ENABLED"),
        "git_commit": os.getenv("GIT_COMMIT") or os.getenv("SOURCE_VERSION"),
    }


def _safe_environment_snapshot() -> dict[str, str | bool | None]:
    return {
        "DATABASE_URL_SET": bool(os.getenv("DATABASE_URL")),
        "POSTGRES_DUAL_WRITE_ENABLED": os.getenv("POSTGRES_DUAL_WRITE_ENABLED"),
        "POSTGRES_READ_ENABLED": os.getenv("POSTGRES_READ_ENABLED"),
        "POSTGRES_DUAL_WRITE_FAIL_OPEN": os.getenv("POSTGRES_DUAL_WRITE_FAIL_OPEN"),
        "SYNC_STOCK_BASICS_ENABLED": os.getenv("SYNC_STOCK_BASICS_ENABLED"),
        "POSTGRES_HOST_SET": bool(os.getenv("POSTGRES_HOST")),
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
        "TRADING_AGENTS_API_BASE_URL_SET": bool(
            os.getenv("TRADING_AGENTS_API_BASE_URL")
        ),
        "TRADING_AGENTS_API_TOKEN_SET": bool(os.getenv("TRADING_AGENTS_API_TOKEN")),
        "TRADING_AGENTS_API_USERNAME_SET": bool(
            os.getenv("TRADING_AGENTS_API_USERNAME")
        ),
        "TRADING_AGENTS_API_PASSWORD_SET": bool(
            os.getenv("TRADING_AGENTS_API_PASSWORD")
        ),
    }


def _validate_explicit_target_environment(
    *,
    include_api_smoke: bool,
    target_env: str | None,
    target_phase: str | None,
) -> tuple[str, str]:
    missing: list[str] = []
    if not (target_env or os.getenv("TRADING_AGENTS_TARGET_ENV")):
        missing.append("TRADING_AGENTS_TARGET_ENV or --target-env")
    effective_phase = target_phase or os.getenv("TRADING_AGENTS_CUTOVER_PHASE")
    if not effective_phase:
        missing.append("TRADING_AGENTS_CUTOVER_PHASE or --target-phase")
    elif effective_phase not in {"pre-read", "post-read", "rollback"}:
        missing.append("TRADING_AGENTS_CUTOVER_PHASE valid value or --target-phase")
    elif effective_phase == "pre-read" and include_api_smoke:
        missing.append("pre-read phase requires --skip-api-smoke")
    elif effective_phase == "post-read" and not include_api_smoke:
        missing.append(
            "post-read phase requires API smoke; do not use --skip-api-smoke"
        )
    elif effective_phase == "rollback":
        missing.append(
            "rollback phase requires postgres_rollback_check.py, not postgres_cutover_gate.py"
        )

    _require_env(missing, "POSTGRES_HOST")
    _require_env(missing, "POSTGRES_DB")

    if not os.getenv("DATABASE_URL"):
        _require_env(missing, "POSTGRES_HOST")
        _require_env(missing, "POSTGRES_DB")
        _require_env(missing, "POSTGRES_USER")
        _require_env(missing, "POSTGRES_PASSWORD")

    if include_api_smoke:
        _require_env(missing, "TRADING_AGENTS_API_BASE_URL")
        has_token = bool(os.getenv("TRADING_AGENTS_API_TOKEN"))
        has_login = bool(os.getenv("TRADING_AGENTS_API_USERNAME")) and bool(
            os.getenv("TRADING_AGENTS_API_PASSWORD")
        )
        if not has_token and not has_login:
            missing.append(
                "TRADING_AGENTS_API_TOKEN or TRADING_AGENTS_API_USERNAME+TRADING_AGENTS_API_PASSWORD"
            )
        _require_env(missing, "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED")
        _require_env(missing, "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED")

    if missing:
        return (
            "failed",
            f"missing explicit target environment: {', '.join(sorted(missing))}",
        )
    return "passed", "explicit target environment present"


def _require_env(missing: list[str], name: str) -> None:
    if not os.getenv(name):
        missing.append(name)


def _evaluate_step_output(
    step: GateStep, output_file: Path, returncode: int
) -> tuple[str, str]:
    if returncode != 0:
        return "failed", f"command exited with {returncode}"
    if step.name == "alembic_offline_sql":
        if output_file.stat().st_size == 0:
            return "failed", "offline SQL output is empty"
        return "passed", "offline SQL generated"

    try:
        payload = _load_json_output(output_file)
    except ValueError as exc:
        return "failed", str(exc)

    validators = {
        "inventory": _validate_inventory,
        "consistency": _validate_consistency,
        "query_plan": _validate_query_plan,
        "data_path_smoke": _validate_all_passed,
        "api_smoke": _validate_all_passed,
        "runtime_log_check": _validate_all_passed,
    }
    validator = validators.get(step.name)
    if validator is None:
        return "passed", "no semantic validator configured"
    return validator(payload)


def _load_json_output(output_file: Path) -> dict:
    text = output_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("JSON output is empty")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse JSON output: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON output is not an object")
    return payload


def _validate_inventory(payload: dict) -> tuple[str, str]:
    if "summary" in payload and isinstance(payload["summary"], dict):
        summary = payload["summary"]
    else:
        summary = payload
    response_dict_count = summary.get("response_model_dict_endpoints")
    raw_request_count = summary.get("raw_dict_request_bodies")
    if response_dict_count != 0:
        return "failed", f"response_model_dict_endpoints={response_dict_count}"
    if raw_request_count != 0:
        return "failed", f"raw_dict_request_bodies={raw_request_count}"
    return "passed", "inventory contract gates passed"


def _validate_consistency(payload: dict) -> tuple[str, str]:
    if payload.get("all_consistent") is not True:
        return "failed", f"all_consistent={payload.get('all_consistent')}"
    return "passed", "consistency gate passed"


def _validate_query_plan(payload: dict) -> tuple[str, str]:
    if payload.get("all_required_without_payload_filter") is not True:
        return (
            "failed",
            f"all_required_without_payload_filter={payload.get('all_required_without_payload_filter')}",
        )
    return "passed", "query plan gate passed"


def _validate_all_passed(payload: dict) -> tuple[str, str]:
    if payload.get("all_passed") is not True:
        return "failed", f"all_passed={payload.get('all_passed')}"
    return "passed", "all checks passed"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PostgreSQL cutover gates and save an evidence bundle."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--sample-limit", type=int, default=500)
    parser.add_argument("--compile-only-query-plan", action="store_true")
    parser.add_argument("--skip-api-smoke", action="store_true")
    parser.add_argument(
        "--runtime-log",
        type=Path,
        help="Optional backend log file to validate as part of the saved cutover evidence bundle.",
    )
    parser.add_argument("--no-require-runtime-startup-gate", action="store_true")
    parser.add_argument("--no-require-runtime-dual-write", action="store_true")
    parser.add_argument("--allow-runtime-dual-write-failures", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--require-explicit-env",
        action="store_true",
        help="Fail before running gates unless target PostgreSQL/PostgreSQL/API environment variables are explicit.",
    )
    parser.add_argument(
        "--target-env",
        help="Non-secret target environment label to write to 00_target_manifest.json.",
    )
    parser.add_argument(
        "--target-phase",
        choices=["pre-read", "post-read", "rollback"],
        help="Cutover phase to write to 00_target_manifest.json.",
    )
    args = parser.parse_args()

    summary = run_gate(
        output_dir=args.output_dir,
        sample_limit=args.sample_limit,
        compile_only_query_plan=args.compile_only_query_plan,
        include_api_smoke=not args.skip_api_smoke,
        runtime_log=args.runtime_log,
        require_runtime_startup_gate=not args.no_require_runtime_startup_gate,
        require_runtime_dual_write=not args.no_require_runtime_dual_write,
        allow_runtime_dual_write_failures=args.allow_runtime_dual_write_failures,
        dry_run=args.dry_run,
        require_explicit_env=args.require_explicit_env,
        target_env=args.target_env,
        target_phase=args.target_phase,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not summary["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
