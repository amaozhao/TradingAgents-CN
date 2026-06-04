import json

import pytest

from scripts.postgres.rollback.check.script import check_rollback_evidence, write_rollback_target_manifest


def test_rollback_check_passes_with_mongo_read_and_healthy_dual_write(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    result = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "true",
        },
    )

    assert result["all_passed"] is True


def test_rollback_check_rejects_postgres_read_enabled(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    result = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "true",
            "POSTGRES_DUAL_WRITE_ENABLED": "true",
        },
    )

    assert result["all_passed"] is False
    assert any(
        check["name"] == "postgres_read_disabled" and check["passed"] is False
        for check in result["checks"]
    )


def test_rollback_check_rejects_failed_api_smoke(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps({"all_passed": False}), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    result = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "true",
        },
    )

    assert result["all_passed"] is False
    assert any(
        check["name"] == "api_smoke_all_passed" and check["passed"] is False
        for check in result["checks"]
    )


def test_rollback_check_requires_explicit_dual_write_disable_allowance(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    result = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "false",
        },
    )
    allowed = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "false",
        },
        allow_dual_write_disabled=True,
    )

    assert result["all_passed"] is False
    assert allowed["all_passed"] is True


def test_rollback_check_requires_migration_state_api_smoke(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps({"all_passed": True, "checks": []}), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    result = check_rollback_evidence(
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "true",
        },
    )

    assert result["all_passed"] is False
    assert any(
        check["name"] == "api_smoke_migration_state" and check["passed"] is False
        for check in result["checks"]
    )


def test_rollback_check_writes_non_secret_target_manifest(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    output_path = write_rollback_target_manifest(
        output_dir=tmp_path,
        target_env="trading_agents-test",
        api_smoke_json=api_smoke,
        consistency_json=consistency,
        env={
            "POSTGRES_READ_ENABLED": "false",
            "POSTGRES_DUAL_WRITE_ENABLED": "true",
            "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED": "false",
            "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED": "true",
            "TRADING_AGENTS_API_TOKEN": "secret-token",
        },
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert output_path == tmp_path / "00_target_manifest.json"
    assert payload["target_env"] == "trading_agents-test"
    assert payload["target_phase"] == "rollback"
    assert payload["include_api_smoke"] is True
    assert payload["postgres_read_enabled"] == "false"
    assert payload["postgres_dual_write_enabled"] == "true"
    assert payload["expected_postgres_read_enabled"] == "false"
    assert payload["expected_postgres_dual_write_enabled"] == "true"
    assert payload["api_smoke_json"] == str(api_smoke)
    assert payload["consistency_json"] == str(consistency)
    assert "secret-token" not in json.dumps(payload)


def test_rollback_manifest_requires_target_environment(tmp_path):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="provide --target-env or TRADING_AGENTS_TARGET_ENV"):
        write_rollback_target_manifest(
            output_dir=tmp_path,
            api_smoke_json=api_smoke,
            consistency_json=consistency,
            env={
                "POSTGRES_READ_ENABLED": "false",
                "POSTGRES_DUAL_WRITE_ENABLED": "true",
            },
        )


def test_rollback_check_cli_reports_missing_target_environment_as_json(tmp_path, monkeypatch, capsys):
    api_smoke = tmp_path / "api_smoke.json"
    consistency = tmp_path / "consistency.json"
    api_smoke.write_text(json.dumps(_api_smoke_payload()), encoding="utf-8")
    consistency.write_text(json.dumps({"all_consistent": True}), encoding="utf-8")
    monkeypatch.delenv("TRADING_AGENTS_TARGET_ENV", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_rollback_check.py",
            "--api-smoke-json",
            str(api_smoke),
            "--consistency-json",
            str(consistency),
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        postgres_rollback_check.main()

    assert exc.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_passed"] is False
    assert payload["checks"][0]["name"] == "target_manifest_env"
    assert "provide --target-env or TRADING_AGENTS_TARGET_ENV" in payload["checks"][0]["detail"]


def _api_smoke_payload() -> dict:
    return {
        "all_passed": True,
        "checks": [
            {
                "name": "migration_state",
                "status": "passed",
                "detail": "ok",
            }
        ],
    }
