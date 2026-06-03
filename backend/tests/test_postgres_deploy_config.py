from pathlib import Path

import pytest

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = [
    REPO_ROOT / "deploy" / "docker" / "compose" / "docker-compose.yml",
    REPO_ROOT / "deploy" / "docker" / "compose" / "docker-compose.hub.nginx.yml",
    REPO_ROOT / "deploy" / "docker" / "compose" / "docker-compose.hub.nginx.arm.yml",
]


@pytest.mark.parametrize("compose_path", COMPOSE_FILES, ids=lambda path: path.name)
def test_docker_compose_includes_postgres_service_and_backend_wiring(compose_path):
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert "postgres" in services
    postgres = services["postgres"]
    assert postgres["image"] == "postgres:16-alpine"
    assert postgres["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U postgres -d tradingagentscn"]
    assert any(volume.endswith(":/var/lib/postgresql/data") for volume in postgres["volumes"])
    if compose_path.name.endswith(".arm.yml"):
        assert postgres["platform"] == "linux/arm64"

    backend = services["backend"]
    backend_env = backend["environment"]
    assert backend_env["POSTGRES_HOST"] == "postgres"
    assert backend_env["POSTGRES_DB"] == "tradingagentscn"
    assert backend_env["POSTGRES_DUAL_WRITE_ENABLED"] == "${POSTGRES_DUAL_WRITE_ENABLED:-false}"
    assert backend_env["POSTGRES_READ_ENABLED"] == "${POSTGRES_READ_ENABLED:-false}"
    assert backend_env["POSTGRES_DUAL_WRITE_FAIL_OPEN"] == "${POSTGRES_DUAL_WRITE_FAIL_OPEN:-true}"
    assert backend_env["SYNC_STOCK_BASICS_ENABLED"] == "${SYNC_STOCK_BASICS_ENABLED:-true}"
    assert backend["depends_on"]["postgres"]["condition"] == "service_healthy"

    volumes = compose["volumes"]
    assert any("postgres" in volume_name for volume_name in volumes)


def test_env_templates_include_postgres_cutover_switches():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    docker_env = (REPO_ROOT / "deploy" / "env" / "docker.env").read_text(encoding="utf-8")

    for text in [env_example, docker_env]:
        assert "POSTGRES_HOST=" in text
        assert "POSTGRES_PORT=" in text
        assert "POSTGRES_USER=" in text
        assert "POSTGRES_PASSWORD=" in text
        assert "POSTGRES_DB=" in text
        assert "POSTGRES_DUAL_WRITE_ENABLED=false" in text
        assert "POSTGRES_READ_ENABLED=false" in text
        assert "POSTGRES_DUAL_WRITE_FAIL_OPEN=true" in text
        assert "SYNC_STOCK_BASICS_ENABLED=true" in text
    assert docker_env.count("SYNC_STOCK_BASICS_ENABLED=") == 1


def test_postgres_phase_env_templates_define_safe_switch_combinations():
    dual_write = (REPO_ROOT / "deploy" / "env" / "postgres-dual-write.env").read_text(encoding="utf-8")
    postgres_read = (REPO_ROOT / "deploy" / "env" / "postgres-read.env").read_text(encoding="utf-8")

    assert "POSTGRES_DUAL_WRITE_ENABLED=true" in dual_write
    assert "POSTGRES_READ_ENABLED=false" in dual_write
    assert "POSTGRES_DUAL_WRITE_FAIL_OPEN=true" in dual_write
    assert "SYNC_STOCK_BASICS_ENABLED=false" in dual_write

    assert "POSTGRES_DUAL_WRITE_ENABLED=true" in postgres_read
    assert "POSTGRES_READ_ENABLED=true" in postgres_read
    assert "POSTGRES_DUAL_WRITE_FAIL_OPEN=false" in postgres_read
    assert "SYNC_STOCK_BASICS_ENABLED=false" in postgres_read


def test_postgres_smoke_env_templates_define_expected_runtime_states():
    pre_read = (REPO_ROOT / "deploy" / "env-templates" / "postgres-pre-read-evidence.env.example").read_text(
        encoding="utf-8"
    )
    post_read = (REPO_ROOT / "deploy" / "env-templates" / "postgres-post-read-smoke.env.example").read_text(
        encoding="utf-8"
    )
    rollback = (REPO_ROOT / "deploy" / "env-templates" / "postgres-rollback-smoke.env.example").read_text(
        encoding="utf-8"
    )

    assert "TRADINGAGENTS_TARGET_ENV=" in pre_read
    assert "TRADINGAGENTS_CUTOVER_PHASE=pre-read" in pre_read
    assert "POSTGRES_DUAL_WRITE_ENABLED=true" in pre_read
    assert "POSTGRES_READ_ENABLED=false" in pre_read
    assert "SYNC_STOCK_BASICS_ENABLED=false" in pre_read
    assert "TRADINGAGENTS_API_TOKEN=" not in pre_read

    for text in [post_read, rollback]:
        assert "TRADINGAGENTS_TARGET_ENV=" in text
        assert "TRADINGAGENTS_API_BASE_URL=https://<target-host>" in text
        assert "TRADINGAGENTS_API_TOKEN=" in text
        assert "TRADINGAGENTS_API_USERNAME=<smoke-user>" in text
        assert "TRADINGAGENTS_API_PASSWORD=<smoke-password>" in text
        assert "TRADINGAGENTS_SMOKE_STOCK_CODE=000001" in text
        assert "TRADINGAGENTS_SMOKE_SYMBOL=000001" in text
        assert "TRADINGAGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true" in text

    assert "TRADINGAGENTS_CUTOVER_PHASE=post-read" in post_read
    assert "TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=true" in post_read

    assert "TRADINGAGENTS_CUTOVER_PHASE=rollback" in rollback
    assert "TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=false" in rollback


def test_backend_dockerfile_installs_pyproject_dependencies():
    dockerfile = (REPO_ROOT / "deploy" / "docker" / "backend.Dockerfile").read_text(encoding="utf-8")

    assert "COPY backend ./backend" in dockerfile
    assert "pip install --prefer-binary ./backend" in dockerfile


def test_cutover_runbook_contains_docker_compose_migration_commands():
    runbook = (REPO_ROOT / "docs" / "migration" / "postgres_cutover_runbook.md").read_text(encoding="utf-8")

    assert "docker compose -f <compose-file> exec backend" in runbook
    assert "--env-file .env --env-file deploy/env/postgres-dual-write.env" in runbook
    assert "--env-file .env --env-file deploy/env/postgres-read.env" in runbook
    assert "cd /app/backend && alembic -c alembic.ini upgrade head" in runbook
    assert "python -m app.db.mongo_to_postgres_migrator" in runbook
    assert (
        "python backend/scripts/postgres_cutover_gate.py --require-explicit-env "
        "--target-env <target-env> --target-phase pre-read --skip-api-smoke"
    ) in runbook
    assert (
        "python backend/scripts/postgres_cutover_evidence_check.py --require-target-manifest "
        "--expected-phase pre-read --require-runtime-log-check "
        "/app/logs/postgres-cutover/pre-read"
    ) in runbook
    assert (
        "python backend/scripts/postgres_cutover_evidence_check.py --require-target-manifest "
        "--expected-phase post-read --require-api-smoke "
        "--require-api-migration-state --require-runtime-log-check /app/logs/postgres-cutover/post-read"
    ) in runbook
    assert "00_target_manifest.json" in runbook
    assert "deploy/env-templates/postgres-pre-read-evidence.env.example" in runbook
    assert "deploy/env-templates/postgres-post-read-smoke.env.example" in runbook
    assert "deploy/env-templates/postgres-rollback-smoke.env.example" in runbook
    assert "TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=true" in runbook
    assert "TRADINGAGENTS_EXPECT_POSTGRES_READ_ENABLED=false" in runbook
    assert "/api/system/config/summary" in runbook
    assert "python backend/scripts/postgres_rollback_check.py" in runbook
    assert "--output-dir /tmp/tradingagents_postgres_cutover_evidence/rollback" in runbook
    assert '--target-env "$TRADINGAGENTS_TARGET_ENV"' in runbook
    assert "python backend/scripts/postgres_cutover_evidence_check.py \\\n  --rollback-only" in runbook
    assert "--require-target-manifest" in runbook
    assert "--expected-phase rollback" in runbook
    assert "--require-rollback-check" in runbook
