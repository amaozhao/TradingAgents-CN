import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.db.migrate import HOT_COLLECTIONS
from scripts import postgres_local_cutover_verify as local_verify
from scripts.postgres.local.cutover.verify.script import (
    LocalServices,
    StepResult,
    _safe_env_snapshot,
    build_verification_steps,
    local_cutover_env,
    local_seed_documents,
    run_local_cutover_verification,
    write_runtime_log_check,
)


def test_local_seed_documents_cover_every_hot_collection():
    assert set(local_seed_documents()) == set(HOT_COLLECTIONS)


def test_build_verification_steps_runs_schema_migrator_and_gate_without_api_by_default(tmp_path):
    steps = build_verification_steps(
        output_dir=tmp_path,
        batch_size=5,
        sample_limit=500,
        include_api_smoke=False,
    )

    assert [step.name for step in steps] == [
        "alembic_upgrade",
        "mongo_to_postgres_migrator",
        "cutover_gate",
        "evidence_bundle_check",
    ]
    assert steps[0].cwd == Path(__file__).resolve().parents[1]
    assert steps[1].command[-2:] == ["--batch-size", "5"]
    gate_command = steps[2].command
    evidence_command = steps[3].command
    assert "--skip-api-smoke" in gate_command
    assert gate_command[-1] == "--skip-api-smoke"
    assert gate_command[gate_command.index("--target-env") + 1] == "local-seeded"
    assert gate_command[gate_command.index("--target-phase") + 1] == "pre-read"
    assert "--require-target-manifest" in evidence_command
    assert evidence_command[evidence_command.index("--expected-phase") + 1] == "pre-read"


def test_build_verification_steps_passes_runtime_log_to_cutover_gate(tmp_path):
    log_path = tmp_path / "backend.log"

    steps = build_verification_steps(
        output_dir=tmp_path,
        batch_size=5,
        sample_limit=500,
        include_api_smoke=False,
        runtime_log=log_path,
        require_runtime_startup_gate=False,
        require_runtime_dual_write=False,
    )

    gate_command = steps[2].command
    evidence_command = steps[3].command
    assert "--runtime-log" in gate_command
    assert gate_command[gate_command.index("--runtime-log") + 1] == str(log_path)
    assert "--no-require-runtime-startup-gate" in gate_command
    assert "--no-require-runtime-dual-write" in gate_command
    assert "--require-runtime-log-check" in evidence_command


def test_build_verification_steps_includes_api_smoke_when_requested(tmp_path):
    steps = build_verification_steps(
        output_dir=tmp_path,
        batch_size=10,
        sample_limit=25,
        include_api_smoke=True,
    )

    gate_command = steps[2].command
    evidence_command = steps[3].command
    assert "--skip-api-smoke" not in gate_command
    assert gate_command[gate_command.index("--sample-limit") + 1] == "25"
    assert gate_command[gate_command.index("--target-phase") + 1] == "post-read"
    assert evidence_command[evidence_command.index("--expected-phase") + 1] == "post-read"
    assert "--require-api-smoke" in evidence_command
    assert "--require-api-migration-state" in evidence_command


def test_local_cutover_env_snapshot_redacts_password_and_token():
    env = local_cutover_env(LocalServices(postgres_password="super-secret-password"))
    env["TRADING_AGENTS_API_BASE_URL"] = "http://127.0.0.1:18080"
    env["TRADING_AGENTS_API_TOKEN"] = "secret-token"

    snapshot = _safe_env_snapshot(env)

    assert snapshot["POSTGRES_PASSWORD_SET"] is True
    assert snapshot["TRADING_AGENTS_API_TOKEN_SET"] is True
    assert "secret-token" not in str(snapshot)
    assert "super-secret-password" not in str(snapshot)


def test_local_services_use_lightweight_postgres_image_by_default():
    services = LocalServices()

    assert services.mongo_image == "mongo:4.4"
    assert services.postgres_image == "postgres:16-alpine"


def test_write_runtime_log_check_writes_gate_artifact(tmp_path):
    log_path = tmp_path / "backend.log"
    log_path.write_text(
        "\n".join(
            [
                "INFO 股票基础信息启动同步已禁用: SYNC_STOCK_BASICS_ENABLED=false",
                "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
            ]
        ),
        encoding="utf-8",
    )

    output_path = write_runtime_log_check(
        runtime_log=log_path,
        output_dir=tmp_path,
        require_startup_gate=True,
        require_dual_write=True,
    )

    assert output_path == tmp_path / "gate" / "runtime_log_check.json"
    assert '"all_passed": true' in output_path.read_text(encoding="utf-8")


def test_write_runtime_log_check_raises_when_gate_fails(tmp_path):
    log_path = tmp_path / "backend.log"
    log_path.write_text("INFO no migration evidence", encoding="utf-8")

    try:
        write_runtime_log_check(
            runtime_log=log_path,
            output_dir=tmp_path,
            require_startup_gate=True,
            require_dual_write=True,
        )
    except RuntimeError as exc:
        assert "runtime log check failed" in str(exc)
    else:
        raise AssertionError("expected runtime log check failure")


def test_local_verifier_summary_points_to_gate_runtime_log_artifact(tmp_path, monkeypatch):
    log_path = tmp_path / "backend.log"
    log_path.write_text(
        "\n".join(
            [
                "INFO 股票基础信息启动同步已禁用: SYNC_STOCK_BASICS_ENABLED=false",
                "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
            ]
        ),
        encoding="utf-8",
    )
    captured: dict[str, list[str]] = {}

    def fake_start_local_containers(services, *, reuse_containers):
        return None

    async def fake_seed_local_mongo(services):
        return {"market_quotes": 1}

    def fake_run_verification_steps(steps, *, env, output_dir):
        captured["gate_command"] = steps[2].command
        captured["evidence_command"] = steps[3].command
        gate_dir = output_dir / "gate"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "runtime_log_check.json").write_text('{"all_passed": true}', encoding="utf-8")
        return [
            StepResult(
                name=step.name,
                command=step.command,
                cwd=str(step.cwd),
                output_file=step.output_file,
                returncode=0,
                status="passed",
            )
            for step in steps
        ]

    monkeypatch.setattr(local_verify, "start_local_containers", fake_start_local_containers)
    monkeypatch.setattr(local_verify, "seed_local_mongo", fake_seed_local_mongo)
    monkeypatch.setattr(local_verify, "run_verification_steps", fake_run_verification_steps)
    monkeypatch.setattr(local_verify, "stop_local_containers", lambda: None)

    summary = asyncio.run(
        run_local_cutover_verification(
            SimpleNamespace(
                output_dir=tmp_path,
                mongo_port=27019,
                mongo_image="mongo:4.4",
                postgres_port=55432,
                postgres_image="postgres:16-alpine",
                api_base_url=None,
                api_token=None,
                batch_size=5,
                sample_limit=500,
                runtime_log=log_path,
                target_env="local-seeded",
                no_require_runtime_startup_gate=False,
                no_require_runtime_dual_write=False,
                reuse_containers=False,
                keep_containers=False,
            )
        )
    )

    assert summary["all_passed"] is True
    assert summary["runtime_log_check"] == str(tmp_path / "gate" / "runtime_log_check.json")
    assert summary["target_manifest"] == str(tmp_path / "gate" / "00_target_manifest.json")
    assert captured["gate_command"][captured["gate_command"].index("--runtime-log") + 1] == str(log_path)
    assert captured["gate_command"][captured["gate_command"].index("--target-env") + 1] == "local-seeded"
    assert captured["gate_command"][captured["gate_command"].index("--target-phase") + 1] == "pre-read"
    assert "--require-target-manifest" in captured["evidence_command"]
    assert captured["evidence_command"][captured["evidence_command"].index("--expected-phase") + 1] == "pre-read"


def test_local_verifier_cleans_up_when_container_start_fails(tmp_path, monkeypatch):
    cleaned = {"called": False}

    def fake_start_local_containers(services, *, reuse_containers):
        raise RuntimeError("port conflict")

    monkeypatch.setattr(local_verify, "start_local_containers", fake_start_local_containers)
    monkeypatch.setattr(local_verify, "stop_local_containers", lambda: cleaned.__setitem__("called", True))

    try:
        asyncio.run(
            run_local_cutover_verification(
                SimpleNamespace(
                    output_dir=tmp_path,
                    mongo_port=27019,
                    mongo_image="mongo:4.4",
                    postgres_port=55432,
                    postgres_image="postgres:16-alpine",
                    api_base_url=None,
                    api_token=None,
                    batch_size=5,
                    sample_limit=500,
                    runtime_log=None,
                    target_env="local-seeded",
                    no_require_runtime_startup_gate=False,
                    no_require_runtime_dual_write=False,
                    reuse_containers=False,
                    keep_containers=False,
                )
            )
        )
    except RuntimeError as exc:
        assert "port conflict" in str(exc)
    else:
        raise AssertionError("expected startup failure")

    assert cleaned["called"] is True
