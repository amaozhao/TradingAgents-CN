from pathlib import Path

from backend.scripts.postgres_runtime_log_check import check_runtime_log


def test_runtime_log_check_accepts_startup_gate_and_dual_write(tmp_path):
    log_path = _write_log(
        tmp_path,
        "\n".join(
            [
                "INFO 股票基础信息启动同步已禁用: SYNC_STOCK_BASICS_ENABLED=false",
                "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
            ]
        ),
    )

    result = check_runtime_log(log_path)

    assert result["all_passed"] is True


def test_runtime_log_check_rejects_missing_startup_gate(tmp_path):
    log_path = _write_log(
        tmp_path,
        "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
    )

    result = check_runtime_log(log_path)

    assert result["all_passed"] is False
    assert _check(result, "startup_stock_basics_disabled")["passed"] is False


def test_runtime_log_check_rejects_dual_write_failures(tmp_path):
    log_path = _write_log(
        tmp_path,
        "\n".join(
            [
                "INFO SYNC_STOCK_BASICS_ENABLED=false",
                "WARNING PostgreSQL dual-write collection=market_quotes status=failed attempted=1 written=0 legacy_ids=market_quotes:akshare:000001 reason=connection lost",
            ]
        ),
    )

    result = check_runtime_log(log_path)

    assert result["all_passed"] is False
    assert _check(result, "dual_write_failures_absent")["passed"] is False


def test_runtime_log_check_rejects_mongo_only_warning(tmp_path):
    log_path = _write_log(
        tmp_path,
        "\n".join(
            [
                "INFO SYNC_STOCK_BASICS_ENABLED=false",
                "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
                "WARNING Mongo-only write retained during PostgreSQL migration: collection=unknown reason=unsupported",
            ]
        ),
    )

    result = check_runtime_log(log_path)

    assert result["all_passed"] is False
    assert _check(result, "mongo_only_writes_absent")["passed"] is False


def test_runtime_log_check_can_relax_startup_gate_for_diagnostics(tmp_path):
    log_path = _write_log(
        tmp_path,
        "INFO PostgreSQL dual-write collection=market_quotes status=written attempted=1 written=1 legacy_ids=market_quotes:akshare:000001 reason=",
    )

    result = check_runtime_log(log_path, require_startup_gate=False)

    assert result["all_passed"] is True


def _write_log(tmp_path: Path, text: str) -> Path:
    log_path = tmp_path / "backend.log"
    log_path.write_text(text, encoding="utf-8")
    return log_path


def _check(result: dict, name: str) -> dict:
    return next(check for check in result["checks"] if check["name"] == name)
