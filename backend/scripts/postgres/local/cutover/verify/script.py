from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.migrate import HOT_COLLECTIONS
from scripts.postgres.log.check.script import check_runtime_log

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

DEFAULT_OUTPUT_ROOT = Path("/tmp/trading_agents_postgres_local_cutover")
POSTGRES_CONTAINER = "ta_pg_migration_test"
LOCAL_DB = "trading_agents_cn"
LOCAL_TARGET_ENV = "local-seeded"


@dataclass(frozen=True)
class LocalServices:
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 55432
    postgres_image: str = "postgres:16-alpine"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = LOCAL_DB


@dataclass(frozen=True)
class VerificationStep:
    name: str
    command: list[str]
    cwd: Path = REPO_ROOT
    output_file: str | None = None


@dataclass
class StepResult:
    name: str
    command: list[str]
    cwd: str
    output_file: str | None
    returncode: int
    status: str


def local_cutover_env(services: LocalServices) -> dict[str, str]:
    return {
        "POSTGRES_HOST": services.postgres_host,
        "POSTGRES_PORT": str(services.postgres_port),
        "POSTGRES_USER": services.postgres_user,
        "POSTGRES_PASSWORD": services.postgres_password,
        "POSTGRES_DB": services.postgres_db,
        "POSTGRES_DUAL_WRITE_ENABLED": "true",
        "POSTGRES_READ_ENABLED": "true",
        "SYNC_STOCK_BASICS_ENABLED": "false",
    }


def build_verification_steps(
    *,
    output_dir: Path,
    batch_size: int,
    sample_limit: int,
    include_api_smoke: bool,
    runtime_log: Path | None = None,
    require_runtime_startup_gate: bool = True,
    require_runtime_dual_write: bool = True,
    target_env: str = LOCAL_TARGET_ENV,
) -> list[VerificationStep]:
    target_phase = "post-read" if include_api_smoke else "pre-read"
    gate_command = [
        sys.executable,
        "backend/scripts/postgres/cutover/gate/script.py",
        "--output-dir",
        str(output_dir / "gate"),
        "--sample-limit",
        str(sample_limit),
        "--target-env",
        target_env,
        "--target-phase",
        target_phase,
    ]
    if not include_api_smoke:
        gate_command.append("--skip-api-smoke")
    if runtime_log is not None:
        gate_command.extend(["--runtime-log", str(runtime_log)])
        if not require_runtime_startup_gate:
            gate_command.append("--no-require-runtime-startup-gate")
        if not require_runtime_dual_write:
            gate_command.append("--no-require-runtime-dual-write")

    evidence_check_command = [
        sys.executable,
        "backend/scripts/postgres/cutover/evidence/check/script.py",
        "--require-target-manifest",
        "--expected-phase",
        target_phase,
    ]
    if include_api_smoke:
        evidence_check_command.extend(
            ["--require-api-smoke", "--require-api-migration-state"]
        )
    if runtime_log is not None:
        evidence_check_command.append("--require-runtime-log-check")
    evidence_check_command.append(str(output_dir / "gate"))

    return [
        VerificationStep(
            name="alembic_upgrade",
            command=["alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            output_file="01_alembic_upgrade.log",
        ),
        VerificationStep(
            name="document_store_to_tables_migrator",
            command=[
                sys.executable,
                "-m",
                "app.core.migrate",
                "--batch-size",
                str(batch_size),
            ],
            cwd=BACKEND_ROOT,
            output_file="02_migrator.json",
        ),
        VerificationStep(
            name="cutover_gate",
            command=gate_command,
            cwd=REPO_ROOT,
            output_file="03_cutover_gate.json",
        ),
        VerificationStep(
            name="evidence_bundle_check",
            command=evidence_check_command,
            cwd=REPO_ROOT,
            output_file="04_evidence_check.json",
        ),
    ]


def write_runtime_log_check(
    *,
    runtime_log: Path,
    output_dir: Path,
    require_startup_gate: bool,
    require_dual_write: bool,
) -> Path:
    result = check_runtime_log(
        runtime_log,
        require_startup_gate=require_startup_gate,
        require_dual_write=require_dual_write,
    )
    output_path = output_dir / "gate" / "runtime_log_check.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not result["all_passed"]:
        raise RuntimeError(f"runtime log check failed: {output_path}")
    return output_path


async def seed_local_postgres(services: LocalServices) -> dict[str, int]:
    create_client = getattr(importlib.import_module("app.db.store"), "create_client")
    client = create_client()
    try:
        db = client[LOCAL_DB]
        await client.admin.command("ping")
        seed_docs = local_seed_documents()
        counts: dict[str, int] = {}
        for collection, documents in seed_docs.items():
            await db[collection].delete_many({})
            if documents:
                result = await db[collection].insert_many(documents)
                counts[collection] = len(result.inserted_ids)
            else:
                counts[collection] = 0
        return counts
    finally:
        client.close()


def local_seed_documents() -> dict[str, list[dict[str, Any]]]:
    """Representative seed data for all first-wave migration collections."""
    return {
        "stock_basic_info": [
            {
                "code": "000001",
                "symbol": "000001",
                "name": "平安银行",
                "source": "tushare",
                "industry": "银行",
                "area": "深圳",
                "market": "主板",
                "total_mv": 1000.0,
                "circ_mv": 900.0,
                "pe": 8.5,
                "pb": 0.9,
                "pe_ttm": 8.8,
                "pb_mrq": 0.95,
            }
        ],
        "market_quotes": [
            {
                "code": "000001",
                "symbol": "000001",
                "source": "tushare",
                "trade_date": "2026-06-03",
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.2,
                "pre_close": 10.0,
                "pct_chg": 2.0,
                "amount": 1000000.0,
                "volume": 100000,
            }
        ],
        "stock_daily_quotes": [
            {
                "symbol": "000001",
                "code": "000001",
                "full_symbol": "000001.SZ",
                "market": "CN",
                "trade_date": "2026-06-03",
                "period": "daily",
                "data_source": "tushare",
                "close": 10.2,
                "pct_chg": 2.0,
                "amount": 1000000.0,
                "volume": 100000,
            }
        ],
        "stock_financial_data": [
            {
                "code": "000001",
                "data_source": "tushare",
                "report_period": "2025Q4",
                "roe": 12.3,
                "roa": 1.1,
                "netprofit_margin": 22.0,
                "gross_margin": 35.0,
            }
        ],
        "stock_news": [
            {
                "symbol": "000001",
                "title": "平安银行新闻",
                "url": "https://example.com/news/1",
                "publish_time": "2026-06-03T10:00:00",
                "data_source": "seed",
                "category": "company",
                "sentiment": "neutral",
                "importance": 3,
            }
        ],
        "analysis_tasks": [
            {
                "task_id": "task-1",
                "user_id": "user-1",
                "stock_code": "000001",
                "status": "completed",
            }
        ],
        "analysis_reports": [
            {
                "analysis_id": "analysis-1",
                "task_id": "task-1",
                "user_id": "user-1",
                "stock_symbol": "000001",
                "summary": "seed summary",
                "recommendation": "hold",
                "status": "completed",
            }
        ],
        "analysis_batches": [
            {"batch_id": "batch-1", "user_id": "user-1", "status": "completed"}
        ],
        "analysis_results": [
            {"legacy_id": "result-1", "task_id": "task-1", "user_id": "user-1"}
        ],
        "sync_status": [{"job": "example_sdk_sync", "status": "completed"}],
        "quotes_ingestion_status": [
            {
                "job": "quotes_ingestion",
                "success": True,
                "data_source": "tushare",
                "records_count": 1,
                "last_sync_time": "2026-06-03T10:00:00+08:00",
            }
        ],
        "scheduler_executions": [
            {"legacy_id": "scheduler-1", "job_id": "tushare_daily", "status": "success"}
        ],
        "scheduler_history": [{"job_id": "tushare_daily", "action": "trigger"}],
        "scheduler_metadata": [{"job_id": "tushare_daily", "display_name": "每日同步"}],
        "system_configs": [
            {"name": "active", "is_active": True, "value": {"enabled": True}}
        ],
        "llm_providers": [{"provider": "dashscope", "enabled": True}],
        "model_catalog": [{"provider": "dashscope", "models": []}],
        "market_categories": [{"id": "a_shares", "enabled": True}],
        "datasource_groupings": [{"id": "akshare_a", "enabled": True}],
        "user_favorites": [
            {
                "user_id": "user-1",
                "favorites": [
                    {"stock_code": "000001", "stock_name": "平安银行", "market": "CN"}
                ],
            }
        ],
        "user_tags": [
            {
                "legacy_id": "tag-1",
                "user_id": "user-1",
                "tag_id": "tag-1",
                "name": "关注",
            }
        ],
        "paper_accounts": [{"user_id": "user-1", "cash": 100000.0}],
        "paper_positions": [{"user_id": "user-1", "code": "000001", "quantity": 100}],
        "paper_orders": [
            {
                "legacy_id": "order-1",
                "user_id": "user-1",
                "code": "000001",
                "status": "filled",
            }
        ],
        "paper_trades": [
            {"legacy_id": "trade-1", "user_id": "user-1", "code": "000001"}
        ],
        "users": [
            {"user_id": "user-1", "username": "admin", "email": "admin@example.com"}
        ],
        "users_collection": [],
        "user_sessions": [
            {
                "session_id": "sess-1",
                "user_id": "user-1",
                "username": "admin",
                "expires_at": "2026-06-04T00:00:00",
            }
        ],
        "login_attempts": [
            {"legacy_id": "attempt-1", "username": "admin", "success": False}
        ],
        "operation_logs": [
            {
                "legacy_id": "log-1",
                "user_id": "user-1",
                "username": "admin",
                "action_type": "user_login",
                "action": "local closeout login smoke",
                "details": {"source": "postgres_local_cutover_verify"},
                "success": True,
                "timestamp": "2026-06-03T10:00:00",
                "created_at": "2026-06-03T10:00:00",
            }
        ],
        "database_backups": [{"legacy_id": "backup-1", "name": "daily"}],
        "notifications": [
            {"legacy_id": "notif-1", "user_id": "user-1", "status": "unread"}
        ],
        "token_usage": [
            {"legacy_id": "usage-1", "provider": "dashscope", "model": "qwen"}
        ],
        "internal_messages": [
            {"message_id": "msg-1", "symbol": "000001", "message_type": "alert"}
        ],
        "social_media_messages": [
            {"message_id": "social-1", "symbol": "000001", "platform": "weibo"}
        ],
    }


def validate_seed_covers_hot_collections() -> None:
    missing = sorted(set(HOT_COLLECTIONS) - set(local_seed_documents()))
    if missing:
        raise RuntimeError(f"local seed is missing HOT_COLLECTIONS entries: {missing}")


def start_local_containers(services: LocalServices, *, reuse_containers: bool) -> None:
    if not reuse_containers:
        _run_docker(["rm", "-f", POSTGRES_CONTAINER], check=False)
    _run_docker(
        [
            "run",
            "-d",
            "--name",
            POSTGRES_CONTAINER,
            "-e",
            f"POSTGRES_PASSWORD={services.postgres_password}",
            "-e",
            f"POSTGRES_DB={services.postgres_db}",
            "-p",
            f"{services.postgres_port}:5432",
            services.postgres_image,
        ],
        check=not reuse_containers,
    )
    _wait_for_port(services.postgres_host, services.postgres_port, timeout_seconds=60)
    _wait_for_postgres_ready(services, timeout_seconds=60)


def stop_local_containers() -> None:
    _run_docker(["rm", "-f", POSTGRES_CONTAINER], check=False)


def run_verification_steps(
    steps: list[VerificationStep],
    *,
    env: dict[str, str],
    output_dir: Path,
) -> list[StepResult]:
    results: list[StepResult] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_env = {**os.environ, **env}

    for step in steps:
        output_file = output_dir / step.output_file if step.output_file else None
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with output_file.open("w", encoding="utf-8") as handle:
                process = subprocess.run(
                    step.command,
                    cwd=step.cwd,
                    env=merged_env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
        else:
            process = subprocess.run(
                step.command, cwd=step.cwd, env=merged_env, text=True, check=False
            )
        status = "passed" if process.returncode == 0 else "failed"
        results.append(
            StepResult(
                name=step.name,
                command=step.command,
                cwd=str(step.cwd),
                output_file=str(output_file) if output_file else None,
                returncode=process.returncode,
                status=status,
            )
        )
        if process.returncode != 0:
            break
    return results


def _run_docker(args: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        text=True,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _wait_for_port(host: str, port: int, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(1)
    raise TimeoutError(f"timed out waiting for {host}:{port}: {last_error}")


def _wait_for_postgres_ready(services: LocalServices, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_output = ""
    while time.monotonic() < deadline:
        process = _run_docker(
            [
                "exec",
                POSTGRES_CONTAINER,
                "pg_isready",
                "-U",
                services.postgres_user,
                "-d",
                services.postgres_db,
            ],
            check=False,
        )
        last_output = process.stdout
        if process.returncode == 0:
            return
        time.sleep(1)
    raise TimeoutError(
        f"timed out waiting for PostgreSQL readiness: {last_output.strip()}"
    )


def _safe_env_snapshot(env: dict[str, str]) -> dict[str, str | bool]:
    return {
        "POSTGRES_HOST": env["POSTGRES_HOST"],
        "POSTGRES_PORT": env["POSTGRES_PORT"],
        "POSTGRES_USER": env["POSTGRES_USER"],
        "POSTGRES_DB": env["POSTGRES_DB"],
        "POSTGRES_PASSWORD_SET": bool(env.get("POSTGRES_PASSWORD")),
        "POSTGRES_DUAL_WRITE_ENABLED": env["POSTGRES_DUAL_WRITE_ENABLED"],
        "POSTGRES_READ_ENABLED": env["POSTGRES_READ_ENABLED"],
        "SYNC_STOCK_BASICS_ENABLED": env["SYNC_STOCK_BASICS_ENABLED"],
        "TRADING_AGENTS_API_BASE_URL_SET": bool(env.get("TRADING_AGENTS_API_BASE_URL")),
        "TRADING_AGENTS_API_TOKEN_SET": bool(env.get("TRADING_AGENTS_API_TOKEN")),
    }


async def run_local_cutover_verification(args: argparse.Namespace) -> dict[str, Any]:
    validate_seed_covers_hot_collections()
    output_dir = args.output_dir
    services = LocalServices(
        postgres_port=args.postgres_port,
        postgres_image=args.postgres_image,
    )
    env = local_cutover_env(services)
    if args.api_base_url:
        env["TRADING_AGENTS_API_BASE_URL"] = args.api_base_url
    if args.api_token:
        env["TRADING_AGENTS_API_TOKEN"] = args.api_token

    try:
        start_local_containers(services, reuse_containers=args.reuse_containers)
        seed_counts = await seed_local_postgres(services)
        steps = build_verification_steps(
            output_dir=output_dir,
            batch_size=args.batch_size,
            sample_limit=args.sample_limit,
            include_api_smoke=bool(args.api_base_url),
            runtime_log=args.runtime_log,
            require_runtime_startup_gate=not args.no_require_runtime_startup_gate,
            require_runtime_dual_write=not args.no_require_runtime_dual_write,
            target_env=args.target_env,
        )
        results = run_verification_steps(steps, env=env, output_dir=output_dir)
        runtime_log_check_path = (
            output_dir / "gate" / "runtime_log_check.json" if args.runtime_log else None
        )
        target_manifest_path = output_dir / "gate" / "00_target_manifest.json"
        summary = {
            "created_at": datetime.now(UTC).isoformat(),
            "all_passed": all(result.status == "passed" for result in results),
            "output_dir": str(output_dir),
            "environment": _safe_env_snapshot(env),
            "seed_counts": seed_counts,
            "results": [asdict(result) for result in results],
            "runtime_log_check": str(runtime_log_check_path)
            if runtime_log_check_path
            else None,
            "target_manifest": str(target_manifest_path),
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return summary
    finally:
        if not args.keep_containers:
            stop_local_containers()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a repeatable local PostgreSQL cutover verification."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--postgres-port", type=int, default=55432)
    parser.add_argument("--postgres-image", default="postgres:16-alpine")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--sample-limit", type=int, default=500)
    parser.add_argument(
        "--api-base-url", help="Optional deployed/local API base URL for API smoke."
    )
    parser.add_argument("--api-token", help="Optional bearer token for API smoke.")
    parser.add_argument(
        "--runtime-log",
        type=Path,
        help="Optional backend log file to validate into gate/runtime_log_check.json.",
    )
    parser.add_argument(
        "--target-env",
        default=LOCAL_TARGET_ENV,
        help="Non-secret target environment label for the nested cutover gate manifest.",
    )
    parser.add_argument("--no-require-runtime-startup-gate", action="store_true")
    parser.add_argument("--no-require-runtime-dual-write", action="store_true")
    parser.add_argument("--reuse-containers", action="store_true")
    parser.add_argument("--keep-containers", action="store_true")
    args = parser.parse_args()

    summary = asyncio.run(run_local_cutover_verification(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not summary["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
