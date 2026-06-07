#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker/compose/docker-compose.yml"

cd "${REPO_ROOT}"
mkdir -p runtime/logs runtime/data

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  echo "backend/.env is required. Copy backend/.env.example to backend/.env and configure it first." >&2
  exit 1
fi

echo "Using backend environment from ${BACKEND_DIR}/.env."

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    local redis_args
    redis_args="$(
      env PYTHONPATH="${BACKEND_DIR}" conda run -n trader python -c '
import shlex

from app.core.config import settings

parts = ["-h", settings.REDIS_HOST, "-p", str(settings.REDIS_PORT)]
if settings.REDIS_PASSWORD:
    parts.extend(["-a", settings.REDIS_PASSWORD, "--no-auth-warning"])
print(" ".join(shlex.quote(part) for part in parts))
'
    )" || return 1
    # shellcheck disable=SC2086
    redis-cli ${redis_args} ping >/dev/null 2>&1
    return
  fi

  env PYTHONPATH="${BACKEND_DIR}" conda run -n trader python -c '
import redis

from app.core.config import settings

client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD or None,
    db=settings.REDIS_DB,
    socket_connect_timeout=2,
    socket_timeout=2,
)
raise SystemExit(0 if client.ping() else 1)
' >/dev/null 2>&1
}

wait_for_redis() {
  local attempts="${1:-30}"

  for _ in $(seq 1 "${attempts}"); do
    if redis_ping; then
      return 0
    fi
    sleep 1
  done

  return 1
}

if ! redis_ping; then
  echo "Redis configured in backend/.env is not reachable; starting the local Docker Compose redis service..."

  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed or not on PATH. Start Redis manually, then rerun this script." >&2
    exit 1
  fi

  docker compose -f "${COMPOSE_FILE}" up -d redis

  if ! wait_for_redis 60; then
    echo "Redis configured in backend/.env did not become ready. Check: docker compose -f ${COMPOSE_FILE} logs redis" >&2
    exit 1
  fi
fi

echo "Redis configured in backend/.env is ready."

cd "${BACKEND_DIR}"
exec env TRADING_AGENTS_LOG_DIR=../runtime/logs PYTHONPATH=. \
  conda run -n trader python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
