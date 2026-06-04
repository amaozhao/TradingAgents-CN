import pytest

from scripts.postgres.consistency.check import script as postgres_consistency_check
from scripts.postgres.migration.inventory import script as postgres_migration_inventory


def test_consistency_check_exits_nonzero_when_report_is_inconsistent(
    monkeypatch, capsys
):
    async def fake_run_cli(sample_limit: int):
        assert sample_limit == 500
        return {"all_consistent": False}

    monkeypatch.setattr(postgres_consistency_check, "_run_cli", fake_run_cli)
    monkeypatch.setattr("sys.argv", ["postgres_consistency_check.py"])

    with pytest.raises(SystemExit) as exc:
        postgres_consistency_check.main()

    assert exc.value.code == 1
    assert '"all_consistent": false' in capsys.readouterr().out


def test_consistency_check_allow_inconsistent_keeps_zero_exit(monkeypatch, capsys):
    async def fake_run_cli(sample_limit: int):
        assert sample_limit == 25
        return {"all_consistent": False}

    monkeypatch.setattr(postgres_consistency_check, "_run_cli", fake_run_cli)
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_consistency_check.py",
            "--sample-limit",
            "25",
            "--allow-inconsistent",
        ],
    )

    postgres_consistency_check.main()

    assert '"all_consistent": false' in capsys.readouterr().out


def test_inventory_exits_nonzero_on_contract_regression(tmp_path, monkeypatch, capsys):
    def fake_scan_backend(root, output):
        assert root == str(tmp_path)
        return {
            "summary": {
                "response_model_dict_endpoints": 1,
                "raw_dict_request_bodies": 0,
            }
        }

    monkeypatch.setattr(postgres_migration_inventory, "scan_backend", fake_scan_backend)
    monkeypatch.setattr(
        "sys.argv", ["postgres_migration_inventory.py", "--root", str(tmp_path)]
    )

    with pytest.raises(SystemExit) as exc:
        postgres_migration_inventory.main()

    assert exc.value.code == 1
    assert '"response_model_dict_endpoints": 1' in capsys.readouterr().out


def test_inventory_allow_contract_regressions_keeps_zero_exit(
    tmp_path, monkeypatch, capsys
):
    def fake_scan_backend(root, output):
        assert root == str(tmp_path)
        return {
            "summary": {
                "response_model_dict_endpoints": 1,
                "raw_dict_request_bodies": 1,
            }
        }

    monkeypatch.setattr(postgres_migration_inventory, "scan_backend", fake_scan_backend)
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_migration_inventory.py",
            "--root",
            str(tmp_path),
            "--allow-contract-regressions",
        ],
    )

    postgres_migration_inventory.main()

    assert '"raw_dict_request_bodies": 1' in capsys.readouterr().out
