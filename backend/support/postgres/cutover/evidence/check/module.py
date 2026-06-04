import json
from pathlib import Path

from scripts.postgres.cutover.evidence.check.script import check_evidence_bundle


def test_evidence_check_passes_complete_bundle(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path)

    assert result["all_passed"] is True


def test_evidence_check_fails_when_summary_is_missing(tmp_path):
    result = check_evidence_bundle(tmp_path)

    assert result["all_passed"] is False
    assert result["checks"][0]["name"] == "summary_exists"


def test_evidence_check_fails_when_required_output_file_is_missing(tmp_path):
    _write_complete_bundle(tmp_path)
    (tmp_path / "03_consistency.json").unlink()

    result = check_evidence_bundle(tmp_path)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "consistency_output_file" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_fails_when_semantic_gate_failed(tmp_path):
    _write_complete_bundle(tmp_path)
    (tmp_path / "04_query_plan.json").write_text(
        json.dumps({"all_required_without_payload_filter": False}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(tmp_path)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "query_plan_semantic" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_requires_api_smoke_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path, require_api_smoke=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "api_smoke_present" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_passes_with_api_smoke_when_requested(tmp_path):
    _write_complete_bundle(tmp_path, include_api_smoke=True)

    result = check_evidence_bundle(tmp_path, require_api_smoke=True)

    assert result["all_passed"] is True


def test_evidence_check_requires_api_migration_state_when_requested(tmp_path):
    _write_complete_bundle(tmp_path, include_api_smoke=True)

    result = check_evidence_bundle(
        tmp_path,
        require_api_smoke=True,
        require_api_migration_state=True,
    )

    assert result["all_passed"] is False
    assert any(
        check["name"] == "api_smoke_migration_state" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_api_migration_state_implies_api_smoke_required(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path, require_api_migration_state=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "api_smoke_present" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_passes_with_api_migration_state_when_requested(tmp_path):
    _write_complete_bundle(
        tmp_path, include_api_smoke=True, include_api_migration_state=True
    )

    result = check_evidence_bundle(
        tmp_path,
        require_api_smoke=True,
        require_api_migration_state=True,
    )

    assert result["all_passed"] is True


def test_evidence_check_requires_runtime_log_check_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path, require_runtime_log_check=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "runtime_log_check_present" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_passes_with_runtime_log_check_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)
    (tmp_path / "runtime_log_check.json").write_text(
        json.dumps({"all_passed": True, "checks": []}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(tmp_path, require_runtime_log_check=True)

    assert result["all_passed"] is True


def test_evidence_check_requires_target_manifest_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path, require_target_manifest=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "target_manifest_present" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_passes_with_expected_target_manifest_phase(tmp_path):
    _write_complete_bundle(
        tmp_path, include_target_manifest=True, target_phase="post-read"
    )

    result = check_evidence_bundle(
        tmp_path,
        require_target_manifest=True,
        expected_phase="post-read",
    )

    assert result["all_passed"] is True


def test_evidence_check_fails_when_target_manifest_phase_does_not_match(tmp_path):
    _write_complete_bundle(
        tmp_path, include_target_manifest=True, target_phase="pre-read"
    )

    result = check_evidence_bundle(
        tmp_path,
        require_target_manifest=True,
        expected_phase="post-read",
    )

    assert result["all_passed"] is False
    assert any(
        check["name"] == "target_manifest_expected_phase" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_uses_runtime_log_step_when_present(tmp_path):
    _write_complete_bundle(tmp_path, include_runtime_log_check=True)
    summary_path = tmp_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["all_passed"] = False
    summary["results"][-1]["status"] = "failed"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    (tmp_path / "runtime_log_check.json").write_text(
        json.dumps({"all_passed": False, "checks": []}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(tmp_path, require_runtime_log_check=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "runtime_log_check_passed" and check["passed"] is False
        for check in result["checks"]
    )
    assert any(
        check["name"] == "runtime_log_check_semantic" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_requires_rollback_check_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)

    result = check_evidence_bundle(tmp_path, require_rollback_check=True)

    assert result["all_passed"] is False
    assert any(
        check["name"] == "rollback_check_present" and check["passed"] is False
        for check in result["checks"]
    )


def test_evidence_check_passes_with_rollback_check_when_requested(tmp_path):
    _write_complete_bundle(tmp_path)
    (tmp_path / "rollback_check.json").write_text(
        json.dumps({"all_passed": True, "checks": []}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(tmp_path, require_rollback_check=True)

    assert result["all_passed"] is True


def test_evidence_check_supports_standalone_rollback_bundle(tmp_path):
    (tmp_path / "rollback_check.json").write_text(
        json.dumps({"all_passed": True, "checks": []}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(tmp_path, rollback_only=True)

    assert result["all_passed"] is True


def test_evidence_check_requires_target_manifest_for_standalone_rollback_bundle(
    tmp_path,
):
    (tmp_path / "00_target_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "created_at": "2026-06-03T00:00:00+00:00",
                "target_env": "trading_agents-test",
                "target_phase": "rollback",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "rollback_check.json").write_text(
        json.dumps({"all_passed": True, "checks": []}),
        encoding="utf-8",
    )

    result = check_evidence_bundle(
        tmp_path,
        rollback_only=True,
        require_target_manifest=True,
        expected_phase="rollback",
    )

    assert result["all_passed"] is True


def _write_complete_bundle(
    output_dir: Path,
    *,
    include_api_smoke: bool = False,
    include_api_migration_state: bool = False,
    include_runtime_log_check: bool = False,
    include_target_manifest: bool = False,
    target_phase: str = "pre-read",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if include_target_manifest:
        (output_dir / "00_target_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "created_at": "2026-06-03T00:00:00+00:00",
                    "target_env": "trading_agents-test",
                    "target_phase": target_phase,
                    "include_api_smoke": include_api_smoke,
                    "runtime_log_included": include_runtime_log_check,
                }
            ),
            encoding="utf-8",
        )
    result_specs = [
        (
            "inventory",
            "01_inventory.json",
            {"response_model_dict_endpoints": 0, "raw_dict_request_bodies": 0},
        ),
        (
            "alembic_offline_sql",
            "02_alembic_offline.sql",
            "CREATE TABLE example(id uuid);",
        ),
        ("consistency", "03_consistency.json", {"all_consistent": True}),
        (
            "query_plan",
            "04_query_plan.json",
            {"all_required_without_payload_filter": True},
        ),
        ("data_path_smoke", "05_data_path_smoke.json", {"all_passed": True}),
    ]
    if include_api_smoke:
        checks = []
        if include_api_migration_state:
            checks.append(
                {"name": "migration_state", "status": "passed", "detail": "ok"}
            )
        result_specs.append(
            ("api_smoke", "06_api_smoke.json", {"all_passed": True, "checks": checks})
        )
    if include_runtime_log_check:
        result_specs.append(
            ("runtime_log_check", "runtime_log_check.json", {"all_passed": True})
        )

    results = []
    for name, filename, payload in result_specs:
        path = output_dir / filename
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        results.append(
            {
                "name": name,
                "status": "passed",
                "output_file": str(path),
                "returncode": 0,
                "command": [],
                "cwd": str(output_dir),
                "detail": "passed",
            }
        )

    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "all_passed": True,
                "dry_run": False,
                "output_dir": str(output_dir),
                "results": results,
            }
        ),
        encoding="utf-8",
    )
