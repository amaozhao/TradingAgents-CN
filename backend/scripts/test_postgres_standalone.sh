#!/usr/bin/env bash

set -euo pipefail

container_name="trading-agents-postgres-standalone-test"
database_name="trading_agents_cn"
password="postgres"
port="${POSTGRES_TEST_PORT:-55432}"

echo "================================================================================"
echo "PostgreSQL standalone smoke test"
echo "================================================================================"

docker rm -f "${container_name}" >/dev/null 2>&1 || true

docker run -d \
  --name "${container_name}" \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD="${password}" \
  -e POSTGRES_DB="${database_name}" \
  -p "${port}:5432" \
  postgres:16-alpine >/dev/null

cleanup() {
  docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Waiting for PostgreSQL on localhost:${port}..."
for _ in $(seq 1 60); do
  if docker exec "${container_name}" pg_isready -U postgres -d "${database_name}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker exec "${container_name}" pg_isready -U postgres -d "${database_name}"
docker exec "${container_name}" psql -U postgres -d "${database_name}" -c "select current_database();" >/dev/null

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT="${port}" \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD="${password}" \
POSTGRES_DB="${database_name}" \
alembic -c alembic.ini upgrade head

POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT="${port}" \
POSTGRES_USER=postgres \
POSTGRES_PASSWORD="${password}" \
POSTGRES_DB="${database_name}" \
python - <<'PY'
from app.db.documentstore import create_sync_client

client = create_sync_client()
try:
    client.admin.command("ping")
    db = client["trading_agents_cn"]
    db["standalone_smoke"].insert_one({"status": "ok"})
    assert db["standalone_smoke"].count_documents({"status": "ok"}) == 1
finally:
    client.close()
PY

echo "PostgreSQL standalone smoke test passed"
