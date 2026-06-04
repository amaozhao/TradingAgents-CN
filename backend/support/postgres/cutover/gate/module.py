import json
import subprocess

from scripts.postgres.cutover.gate.script import build_gate_steps, run_gate


def test_build_gate_steps_includes_required_cutover_gates():
    steps = build_gate_steps(
        sample_limit=250, compile_only_query_plan=True, include_api_smoke=True
    )

    assert [step.name for step in steps] == [
        "inventory",
        "alembic_offline_sql",
        "consistency",
        "query_plan",
        "data_path_smoke",
        "api_smoke",
    ]
    assert steps[2].command[-2:] == ["--sample-limit", "250"]
    assert steps[3].command[-1] == "--compile-only"


def test_build_gate_steps_can_include_runtime_log_check(tmp_path):
    log_path = tmp_path / "backend.log"

    steps = build_gate_steps(
        sample_limit=250,
        compile_only_query_plan=True,
        include_api_smoke=False,
        runtime_log=log_path,
        require_runtime_startup_gate=False,
        require_runtime_dual_write=False,
        allow_runtime_dual_write_failures=True,
        allow_runtime_postgres_only=True,
    )

    assert [step.name for step in steps] == [
        "inventory",
        "alembic_offline_sql",
        "consistency",
        "query_plan",
        "data_path_smoke",
        "runtime_log_check",
    ]
    runtime_step = steps[-1]
    assert runtime_step.output_file == "runtime_log_check.json"
    assert (
        "backend/scripts/postgres/runtime/log/check/script.py" in runtime_step.command
    )
    assert str(log_path) in runtime_step.command
    assert "--no-require-startup-gate" in runtime_step.command
    assert "--no-require-dual-write" in runtime_step.command
    assert "--allow-dual-write-failures" in runtime_step.command
    assert "--allow-postgres-only" in runtime_step.command


def test_cutover_gate_dry_run_writes_summary_without_running_commands(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-postgres")
    monkeypatch.setenv("TRADING_AGENTS_API_TOKEN", "secret-token")
    monkeypatch.setenv("TRADING_AGENTS_API_BASE_URL", "https://example.invalid")

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=True,
        include_api_smoke=False,
        dry_run=True,
    )

    assert summary["all_passed"] is True
    assert [result["status"] for result in summary["results"]] == ["dry_run"] * 5
    assert summary["environment"]["TRADING_AGENTS_API_TOKEN_SET"] is True
    assert "secret-token" not in json.dumps(summary)
    assert "secret-postgres" not in json.dumps(summary)
    assert (tmp_path / "summary.json").exists()


def test_cutover_gate_dry_run_records_runtime_log_step_without_reading_log(tmp_path):
    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=True,
        include_api_smoke=False,
        runtime_log=tmp_path / "missing.log",
        dry_run=True,
    )

    assert summary["all_passed"] is True
    assert summary["results"][-1]["name"] == "runtime_log_check"
    assert summary["results"][-1]["status"] == "dry_run"
    assert summary["results"][-1]["output_file"].endswith("runtime_log_check.json")


def test_cutover_gate_writes_non_secret_target_manifest_when_target_is_named(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-postgres")
    monkeypatch.setenv("TRADING_AGENTS_API_TOKEN", "secret-token")
    monkeypatch.setenv("POSTGRES_READ_ENABLED", "true")
    monkeypatch.setenv("POSTGRES_DUAL_WRITE_ENABLED", "true")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED", "true")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED", "true")

    run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=True,
        include_api_smoke=True,
        runtime_log=tmp_path / "backend.log",
        dry_run=True,
        target_env="trading_agents-test",
        target_phase="post-read",
    )

    manifest = json.loads(
        (tmp_path / "00_target_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["target_env"] == "trading_agents-test"
    assert manifest["target_phase"] == "post-read"
    assert manifest["include_api_smoke"] is True
    assert manifest["runtime_log_included"] is True
    assert manifest["postgres_read_enabled"] == "true"
    assert "secret-token" not in json.dumps(manifest)
    assert "secret-postgres" not in json.dumps(manifest)


def test_cutover_gate_require_explicit_env_fails_fast_when_target_env_missing(
    tmp_path, monkeypatch
):
    for name in [
        "DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_DB",
        "POSTGRES_HOST",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "TRADING_AGENTS_API_BASE_URL",
        "TRADING_AGENTS_API_TOKEN",
        "TRADING_AGENTS_API_USERNAME",
        "TRADING_AGENTS_API_PASSWORD",
        "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED",
        "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED",
        "TRADING_AGENTS_TARGET_ENV",
        "TRADING_AGENTS_CUTOVER_PHASE",
    ]:
        monkeypatch.delenv(name, raising=False)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=True,
        dry_run=False,
        require_explicit_env=True,
    )

    assert summary["all_passed"] is False
    assert [result["name"] for result in summary["results"]] == ["target_env_preflight"]
    assert summary["results"][0]["status"] == "failed"
    assert "POSTGRES_HOST" in summary["results"][0]["detail"]
    assert "POSTGRES_PASSWORD" in summary["results"][0]["detail"]
    assert "TRADING_AGENTS_API_BASE_URL" in summary["results"][0]["detail"]
    assert (
        "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED" in summary["results"][0]["detail"]
    )
    assert (
        "TRADING_AGENTS_TARGET_ENV or --target-env" in summary["results"][0]["detail"]
    )
    assert (
        "TRADING_AGENTS_CUTOVER_PHASE or --target-phase"
        in summary["results"][0]["detail"]
    )
    assert not (tmp_path / "00_target_manifest.json").exists()


def test_cutover_gate_does_not_write_incomplete_manifest_when_preflight_fails(
    tmp_path, monkeypatch
):
    _set_required_target_env(monkeypatch)
    monkeypatch.delenv("TRADING_AGENTS_TARGET_ENV", raising=False)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=True,
        dry_run=False,
        require_explicit_env=True,
        target_phase="post-read",
    )

    assert summary["all_passed"] is False
    assert (
        "TRADING_AGENTS_TARGET_ENV or --target-env" in summary["results"][0]["detail"]
    )
    assert not (tmp_path / "00_target_manifest.json").exists()


def test_cutover_gate_require_explicit_env_passes_and_runs_gates_with_target_env(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("POSTGRES_HOST", "postgres.example.internal")
    monkeypatch.setenv("POSTGRES_DB", "trading_agents_cn")
    monkeypatch.setenv("POSTGRES_HOST", "postgres.example.internal")
    monkeypatch.setenv("POSTGRES_DB", "trading_agents_cn")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-postgres")
    monkeypatch.setenv("TRADING_AGENTS_API_BASE_URL", "https://api.example.internal")
    monkeypatch.setenv("TRADING_AGENTS_API_TOKEN", "secret-token")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED", "true")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED", "true")

    def fake_run(command, cwd, stdout, stderr, text, check):
        command_text = " ".join(command)
        if "postgres_migration_inventory.py" in command_text:
            stdout.write(
                json.dumps(
                    {"response_model_dict_endpoints": 0, "raw_dict_request_bodies": 0}
                )
            )
        elif "postgres_consistency_check.py" in command_text:
            stdout.write(json.dumps({"all_consistent": True}))
        elif "postgres_query_plan_check.py" in command_text:
            stdout.write(json.dumps({"all_required_without_payload_filter": True}))
        elif "postgres_cutover_smoke.py" in command_text:
            stdout.write(json.dumps({"all_passed": True}))
        elif "postgres_api_smoke.py" in command_text:
            stdout.write(
                json.dumps(
                    {
                        "all_passed": True,
                        "checks": [
                            {
                                "name": "migration_state",
                                "status": "passed",
                                "detail": "ok",
                            }
                        ],
                    }
                )
            )
        elif "postgres_runtime_log_check.py" in command_text:
            stdout.write(json.dumps({"all_passed": True}))
        else:
            stdout.write("offline sql")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=True,
        runtime_log=tmp_path / "backend.log",
        dry_run=False,
        require_explicit_env=True,
        target_env="trading_agents-test",
        target_phase="post-read",
    )

    assert summary["all_passed"] is True
    assert summary["results"][0]["name"] == "target_env_preflight"
    assert summary["results"][0]["status"] == "passed"
    assert summary["results"][-1]["name"] == "runtime_log_check"
    assert summary["results"][-1]["status"] == "passed"
    assert "secret-token" not in json.dumps(summary)
    assert "secret-postgres" not in json.dumps(summary)


def test_cutover_gate_rejects_post_read_without_api_smoke(tmp_path, monkeypatch):
    _set_required_target_env(monkeypatch)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=False,
        dry_run=False,
        require_explicit_env=True,
        target_env="trading_agents-test",
        target_phase="post-read",
    )

    assert summary["all_passed"] is False
    assert summary["results"][0]["name"] == "target_env_preflight"
    assert "post-read phase requires API smoke" in summary["results"][0]["detail"]


def test_cutover_gate_rejects_pre_read_with_api_smoke(tmp_path, monkeypatch):
    _set_required_target_env(monkeypatch)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=True,
        dry_run=False,
        require_explicit_env=True,
        target_env="trading_agents-test",
        target_phase="pre-read",
    )

    assert summary["all_passed"] is False
    assert summary["results"][0]["name"] == "target_env_preflight"
    assert "pre-read phase requires --skip-api-smoke" in summary["results"][0]["detail"]


def test_cutover_gate_rejects_rollback_phase_for_cutover_gate(tmp_path, monkeypatch):
    _set_required_target_env(monkeypatch)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=False,
        include_api_smoke=True,
        dry_run=False,
        require_explicit_env=True,
        target_env="trading_agents-test",
        target_phase="rollback",
    )

    assert summary["all_passed"] is False
    assert summary["results"][0]["name"] == "target_env_preflight"
    assert (
        "rollback phase requires postgres_rollback_check.py"
        in summary["results"][0]["detail"]
    )


def test_cutover_gate_fails_when_successful_consistency_command_reports_inconsistent_json(
    tmp_path, monkeypatch
):
    def fake_run(command, cwd, stdout, stderr, text, check):
        command_text = " ".join(command)
        if "postgres_consistency_check.py" in command_text:
            stdout.write(json.dumps({"all_consistent": False}))
        elif "postgres_migration_inventory.py" in command_text:
            stdout.write(
                json.dumps(
                    {"response_model_dict_endpoints": 0, "raw_dict_request_bodies": 0}
                )
            )
        elif "postgres_query_plan_check.py" in command_text:
            stdout.write(json.dumps({"all_required_without_payload_filter": True}))
        elif "postgres_cutover_smoke.py" in command_text:
            stdout.write(json.dumps({"all_passed": True}))
        else:
            stdout.write("offline sql")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=True,
        include_api_smoke=False,
        dry_run=False,
    )

    consistency = next(
        result for result in summary["results"] if result["name"] == "consistency"
    )
    assert summary["all_passed"] is False
    assert consistency["status"] == "failed"
    assert "all_consistent" in consistency["detail"]


def test_cutover_gate_fails_when_successful_smoke_command_reports_failed_checks(
    tmp_path, monkeypatch
):
    def fake_run(command, cwd, stdout, stderr, text, check):
        command_text = " ".join(command)
        if "postgres_migration_inventory.py" in command_text:
            stdout.write(
                json.dumps(
                    {"response_model_dict_endpoints": 0, "raw_dict_request_bodies": 0}
                )
            )
        elif "postgres_consistency_check.py" in command_text:
            stdout.write(json.dumps({"all_consistent": True}))
        elif "postgres_query_plan_check.py" in command_text:
            stdout.write(json.dumps({"all_required_without_payload_filter": True}))
        elif "postgres_cutover_smoke.py" in command_text:
            stdout.write(json.dumps({"all_passed": False}))
        else:
            stdout.write("offline sql")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = run_gate(
        output_dir=tmp_path,
        sample_limit=500,
        compile_only_query_plan=True,
        include_api_smoke=False,
        dry_run=False,
    )

    smoke = next(
        result for result in summary["results"] if result["name"] == "data_path_smoke"
    )
    assert summary["all_passed"] is False
    assert smoke["status"] == "failed"
    assert "all_passed" in smoke["detail"]


def _set_required_target_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "postgres.example.internal")
    monkeypatch.setenv("POSTGRES_DB", "trading_agents_cn")
    monkeypatch.setenv("POSTGRES_HOST", "postgres.example.internal")
    monkeypatch.setenv("POSTGRES_DB", "trading_agents_cn")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-postgres")
    monkeypatch.setenv("TRADING_AGENTS_API_BASE_URL", "https://api.example.internal")
    monkeypatch.setenv("TRADING_AGENTS_API_TOKEN", "secret-token")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED", "true")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED", "true")
