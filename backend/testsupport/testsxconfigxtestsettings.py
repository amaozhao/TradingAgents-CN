from app.core.coreconfig import Settings


def test_settings_defaults_and_env_override(monkeypatch):
    # Override a few env vars
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("MONGODB_USERNAME", "user")
    monkeypatch.setenv("MONGODB_PASSWORD", "pass")
    monkeypatch.setenv("MONGODB_HOST", "dbhost")
    monkeypatch.setenv("MONGODB_PORT", "27018")
    monkeypatch.setenv("MONGODB_DATABASE", "testdb")
    monkeypatch.setenv("MONGODB_AUTH_SOURCE", "admin")

    s = Settings()  # instantiate fresh to pick up env

    assert s.PORT == 8123
    assert s.DEBUG is False

    # URI should include credentials when provided
    uri = s.MONGO_URI
    assert uri.startswith("mongodb://user:pass@dbhost:27018/")
    assert uri.endswith("testdb?authSource=admin")


def test_redis_url_builds(monkeypatch):
    # Without password
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "2")
    # Ensure no password from .env leaks into this test
    monkeypatch.setenv("REDIS_PASSWORD", "")

    s = Settings()
    assert s.REDIS_URL == "redis://127.0.0.1:6379/2"

    # With password
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss")
    s = Settings()
    assert s.REDIS_URL == "redis://:p@ss@127.0.0.1:6379/2"


def test_postgres_url_uses_explicit_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading",
    )
    monkeypatch.setenv("POSTGRES_HOST", "ignored-host")
    monkeypatch.setenv("POSTGRES_PORT", "9999")

    s = Settings()

    assert s.POSTGRES_URL == "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading"
    assert s.DATABASE_URL == "postgresql+asyncpg://pguser:pgpass@pg-host:15432/trading"


def test_postgres_url_builds_from_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "trader")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "tradingagents_test")

    s = Settings()

    assert s.POSTGRES_URL == "postgresql+asyncpg://trader:secret@127.0.0.1:5433/tradingagents_test"


def test_postgres_url_uses_safe_default_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    s = Settings()

    assert s.POSTGRES_URL == "postgresql+asyncpg://postgres:postgres@localhost:5432/tradingagentscn"
