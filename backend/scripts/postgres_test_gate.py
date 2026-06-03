from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class TestStep:
    name: str
    command: list[str]
    cwd: Path = REPO_ROOT


@dataclass(frozen=True)
class TestStepResult:
    name: str
    command: list[str]
    cwd: str
    returncode: int
    status: str


def build_scope_steps(scopes: Iterable[str]) -> list[TestStep]:
    selected = list(scopes)
    unknown = [scope for scope in selected if scope not in SCOPE_STEPS]
    if unknown:
        raise ValueError(f"unknown scope(s): {', '.join(sorted(unknown))}")

    steps: list[TestStep] = []
    seen: set[tuple[str, tuple[str, ...], Path]] = set()
    for scope in selected:
        for step in SCOPE_STEPS[scope]:
            key = (step.name, tuple(step.command), step.cwd)
            if key not in seen:
                steps.append(step)
                seen.add(key)
    return steps


def run_test_gate(scopes: Iterable[str], *, dry_run: bool = False) -> dict:
    steps = build_scope_steps(scopes)
    results: list[TestStepResult] = []
    for step in steps:
        if dry_run:
            results.append(
                TestStepResult(
                    name=step.name,
                    command=step.command,
                    cwd=str(step.cwd),
                    returncode=0,
                    status="dry_run",
                )
            )
            continue
        process = subprocess.run(step.command, cwd=step.cwd, text=True, check=False)
        status = "passed" if process.returncode == 0 else "failed"
        results.append(
            TestStepResult(
                name=step.name,
                command=step.command,
                cwd=str(step.cwd),
                returncode=process.returncode,
                status=status,
            )
        )
        if process.returncode != 0:
            break
    return {
        "all_passed": all(result.status in {"passed", "dry_run"} for result in results),
        "dry_run": dry_run,
        "scopes": list(scopes),
        "results": [asdict(result) for result in results],
    }


PYTHON = sys.executable

SCRIPT_COMPILE_STEP = TestStep(
    name="postgres_script_py_compile",
    command=[
        PYTHON,
        "-m",
        "py_compile",
        "backend/scripts/postgres_api_smoke.py",
        "backend/scripts/postgres_consistency_check.py",
        "backend/scripts/postgres_cutover_evidence_check.py",
        "backend/scripts/postgres_cutover_gate.py",
        "backend/scripts/postgres_cutover_smoke.py",
        "backend/scripts/postgres_local_cutover_verify.py",
        "backend/scripts/postgres_migration_inventory.py",
        "backend/scripts/postgres_query_plan_check.py",
        "backend/scripts/postgres_rollback_check.py",
        "backend/scripts/postgres_runtime_log_check.py",
        "backend/scripts/postgres_test_gate.py",
    ],
)

SCOPE_STEPS: dict[str, list[TestStep]] = {
    "quick": [
        SCRIPT_COMPILE_STEP,
        TestStep(
            name="migration_docs_and_inventory",
            command=[
                PYTHON,
                "-m",
                "pytest",
                "backend/tests/test_migration_docs_integrity.py",
                "backend/tests/test_postgres_migration_inventory.py",
                "-q",
            ],
        ),
    ],
    "api-contract": [
        TestStep(
            name="api_contract_tests",
            command=[
                PYTHON,
                "-m",
                "pytest",
                "backend/tests/test_router_request_models.py",
                "backend/tests/test_router_response_model_coverage.py",
                "backend/tests/test_postgres_migration_inventory.py",
                "backend/tests/test_openapi_import_boundary.py",
                "-q",
            ],
        ),
        TestStep(
            name="inventory_contract_scan",
            command=[
                PYTHON,
                "backend/scripts/postgres_migration_inventory.py",
                "--output",
                "docs/migration/postgres_inventory.json",
            ],
        ),
    ],
    "cutover": [
        SCRIPT_COMPILE_STEP,
        TestStep(
            name="cutover_gate_tests",
            command=[
                PYTHON,
                "-m",
                "pytest",
                "backend/tests/test_postgres_cutover_gate.py",
                "backend/tests/test_postgres_cutover_evidence_check.py",
                "backend/tests/test_postgres_runtime_log_check.py",
                "backend/tests/test_postgres_deploy_config.py",
                "-q",
            ],
        ),
    ],
    "rollback": [
        SCRIPT_COMPILE_STEP,
        TestStep(
            name="rollback_gate_tests",
            command=[
                PYTHON,
                "-m",
                "pytest",
                "backend/tests/db/test_postgres_api_smoke.py",
                "backend/tests/test_postgres_rollback_check.py",
                "backend/tests/test_postgres_cutover_evidence_check.py",
                "backend/tests/test_postgres_deploy_config.py",
                "-q",
            ],
        ),
    ],
    "docs": [
        TestStep(
            name="migration_document_tests",
            command=[
                PYTHON,
                "-m",
                "pytest",
                "backend/tests/test_migration_docs_integrity.py",
                "backend/tests/test_postgres_deploy_config.py",
                "-q",
            ],
        ),
    ],
    "db": [
        TestStep(
            name="postgres_db_tests",
            command=[PYTHON, "-m", "pytest", "backend/tests/db", "backend/tests/config", "-q"],
        ),
    ],
    "full": [
        TestStep(
            name="backend_full_pytest",
            command=[PYTHON, "-m", "pytest", "-q"],
            cwd=BACKEND_ROOT,
        ),
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run scoped PostgreSQL migration verification gates without defaulting to full pytest."
    )
    parser.add_argument(
        "--scope",
        action="append",
        choices=sorted(SCOPE_STEPS),
        default=None,
        help="Verification scope to run. Repeat for multiple scopes. Default: quick.",
    )
    parser.add_argument("--list-scopes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_scopes:
        print(json.dumps({"scopes": sorted(SCOPE_STEPS)}, indent=2, sort_keys=True))
        return

    scopes = args.scope or ["quick"]
    result = run_test_gate(scopes, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
