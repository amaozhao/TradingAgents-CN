import pytest
import yaml

from support.path import REPO_ROOT

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
    assert postgres["image"] == "postgres:alpine"
    assert postgres["healthcheck"]["test"] == [
        "CMD-SHELL",
        "pg_isready -U postgres -d trading_agents_cn",
    ]
    assert any(
        volume.endswith(":/var/lib/postgresql") for volume in postgres["volumes"]
    )
    if compose_path.name.endswith(".arm.yml"):
        assert postgres["platform"] == "linux/arm64"

    backend = services["backend"]
    backend_env = backend["environment"]
    assert backend_env["POSTGRES_HOST"] == "postgres"
    assert backend_env["POSTGRES_DB"] == "trading_agents_cn"
    assert (
        backend_env["POSTGRES_DUAL_WRITE_ENABLED"]
        == "${POSTGRES_DUAL_WRITE_ENABLED:-true}"
    )
    assert backend_env["POSTGRES_READ_ENABLED"] == "${POSTGRES_READ_ENABLED:-true}"
    assert (
        backend_env["POSTGRES_DUAL_WRITE_FAIL_OPEN"]
        == "${POSTGRES_DUAL_WRITE_FAIL_OPEN:-true}"
    )
    assert (
        backend_env["SYNC_STOCK_BASICS_ENABLED"] == "${SYNC_STOCK_BASICS_ENABLED:-true}"
    )
    assert backend["depends_on"]["postgres"]["condition"] == "service_healthy"

    volumes = compose["volumes"]
    assert any("postgres" in volume_name for volume_name in volumes)


def test_env_templates_include_postgres_cutover_switches():
    env_example = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    docker_env = (REPO_ROOT / "deploy" / "env" / "docker.env").read_text(
        encoding="utf-8"
    )

    for text in [env_example, docker_env]:
        assert "POSTGRES_HOST=" in text
        assert "POSTGRES_PORT=" in text
        assert "POSTGRES_USER=" in text
        assert "POSTGRES_PASSWORD=" in text
        assert "POSTGRES_DB=" in text
        assert "POSTGRES_DUAL_WRITE_ENABLED=true" in text
        assert "POSTGRES_READ_ENABLED=true" in text
        assert "POSTGRES_DUAL_WRITE_FAIL_OPEN=true" in text
        assert "SYNC_STOCK_BASICS_ENABLED=true" in text
    assert docker_env.count("SYNC_STOCK_BASICS_ENABLED=") == 1


def test_postgres_phase_env_templates_define_safe_switch_combinations():
    pre_read = (
        REPO_ROOT
        / "deploy"
        / "env-templates"
        / "postgres-pre-read-evidence.env.example"
    ).read_text(encoding="utf-8")
    post_read = (
        REPO_ROOT / "deploy" / "env-templates" / "postgres-post-read-smoke.env.example"
    ).read_text(encoding="utf-8")
    rollback = (
        REPO_ROOT / "deploy" / "env-templates" / "postgres-rollback-smoke.env.example"
    ).read_text(encoding="utf-8")

    assert "POSTGRES_DUAL_WRITE_ENABLED=true" in pre_read
    assert "POSTGRES_READ_ENABLED=false" in pre_read
    assert "SYNC_STOCK_BASICS_ENABLED=false" in pre_read

    assert "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true" in post_read
    assert "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED=true" in post_read

    assert "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true" in rollback
    assert "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED=false" in rollback


def test_postgres_smoke_env_templates_define_expected_runtime_states():
    pre_read = (
        REPO_ROOT
        / "deploy"
        / "env-templates"
        / "postgres-pre-read-evidence.env.example"
    ).read_text(encoding="utf-8")
    post_read = (
        REPO_ROOT / "deploy" / "env-templates" / "postgres-post-read-smoke.env.example"
    ).read_text(encoding="utf-8")
    rollback = (
        REPO_ROOT / "deploy" / "env-templates" / "postgres-rollback-smoke.env.example"
    ).read_text(encoding="utf-8")

    assert "TRADING_AGENTS_TARGET_ENV=" in pre_read
    assert "TRADING_AGENTS_CUTOVER_PHASE=pre-read" in pre_read
    assert "POSTGRES_DUAL_WRITE_ENABLED=true" in pre_read
    assert "POSTGRES_READ_ENABLED=false" in pre_read
    assert "SYNC_STOCK_BASICS_ENABLED=false" in pre_read
    assert "TRADING_AGENTS_API_TOKEN=" not in pre_read

    for text in [post_read, rollback]:
        assert "TRADING_AGENTS_TARGET_ENV=" in text
        assert "TRADING_AGENTS_API_BASE_URL=https://<target-host>" in text
        assert "TRADING_AGENTS_API_TOKEN=" in text
        assert "TRADING_AGENTS_API_USERNAME=<smoke-user>" in text
        assert "TRADING_AGENTS_API_PASSWORD=<smoke-password>" in text
        assert "TRADING_AGENTS_SMOKE_STOCK_CODE=000001" in text
        assert "TRADING_AGENTS_SMOKE_SYMBOL=000001" in text
        assert "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED=true" in text

    assert "TRADING_AGENTS_CUTOVER_PHASE=post-read" in post_read
    assert "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED=true" in post_read

    assert "TRADING_AGENTS_CUTOVER_PHASE=rollback" in rollback
    assert "TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED=false" in rollback


def test_backend_dockerfile_installs_pyproject_dependencies():
    dockerfile = (REPO_ROOT / "deploy" / "docker" / "backend.Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "COPY backend ./backend" in dockerfile
    assert "pip install --prefer-binary ./backend" in dockerfile
