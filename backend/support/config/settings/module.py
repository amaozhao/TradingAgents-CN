from app.core.config import Settings


def test_settings_defaults_and_env_override(monkeypatch):
    # Override a few env vars
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pass")
    monkeypatch.setenv("POSTGRES_HOST", "dbhost")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    s = Settings()  # instantiate fresh to pick up env

    assert s.PORT == 8123
    assert s.DEBUG is False

    assert s.postgres_url == "postgresql+asyncpg://user:pass@dbhost:5433/testdb"


def test_redis_url_builds(monkeypatch):
    # Without password
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "2")
    # Ensure no password from .env leaks into this test
    monkeypatch.setenv("REDIS_PASSWORD", "")

    s = Settings(_env_file=None)
    assert s.redis_url == "redis://127.0.0.1:6379/2"

    # With password
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss")
    s = Settings(_env_file=None)
    assert s.redis_url == "redis://:p@ss@127.0.0.1:6379/2"


def test_postgres_url_uses_explicit_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading",
    )
    monkeypatch.setenv("POSTGRES_HOST", "ignored-host")
    monkeypatch.setenv("POSTGRES_PORT", "9999")

    s = Settings()

    assert s.postgres_url == "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading"
    assert s.DATABASE_URL == "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading"


def test_postgres_url_builds_from_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "trader")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "trading_agents_test")

    s = Settings()

    assert (
        s.postgres_url
        == "postgresql+asyncpg://trader:secret@127.0.0.1:5433/trading_agents_test"
    )


def test_postgres_url_uses_safe_default_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    s = Settings(_env_file=None)

    assert (
        s.postgres_url
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_agents_cn"
    )
