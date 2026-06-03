import subprocess

import pytest

from scripts import postgres_test_gate


def test_test_gate_defaults_to_quick_scope_without_full_pytest():
    result = postgres_test_gate.run_test_gate(["quick"], dry_run=True)

    assert result["all_passed"] is True
    assert result["scopes"] == ["quick"]
    commands = [" ".join(item["command"]) for item in result["results"]]
    assert not any(command.endswith(" -m pytest -q") for command in commands)


def test_test_gate_full_scope_is_explicit():
    result = postgres_test_gate.run_test_gate(["full"], dry_run=True)

    assert [item["name"] for item in result["results"]] == ["backend_full_pytest"]
    assert result["results"][0]["cwd"].endswith("/backend")


def test_test_gate_deduplicates_shared_compile_step():
    result = postgres_test_gate.run_test_gate(["cutover", "rollback"], dry_run=True)

    names = [item["name"] for item in result["results"]]
    assert names.count("postgres_script_py_compile") == 1
    assert "cutover_gate_tests" in names
    assert "rollback_gate_tests" in names


def test_test_gate_rejects_unknown_scope():
    with pytest.raises(ValueError):
        postgres_test_gate.build_scope_steps(["missing"])


def test_test_gate_stops_after_first_failed_step(monkeypatch):
    calls = []

    def fake_run(command, cwd, text, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = postgres_test_gate.run_test_gate(["quick"])

    assert result["all_passed"] is False
    assert len(result["results"]) == 1
    assert len(calls) == 1
