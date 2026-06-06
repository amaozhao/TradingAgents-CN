#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker/compose/docker-compose.yml"

cd "${REPO_ROOT}"
mkdir -p runtime/logs runtime/data

if [[ -f "${BACKEND_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.env"
  set +a
fi

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
REDIS_DB="${REDIS_DB:-0}"

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    if [[ -n "${REDIS_PASSWORD}" ]]; then
      redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" --no-auth-warning ping >/dev/null 2>&1
    else
      redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping >/dev/null 2>&1
    fi
    return $?
  fi

  conda run -n trader python -c \
    'import sys, redis; host, port, password, db = sys.argv[1], int(sys.argv[2]), sys.argv[3] or None, int(sys.argv[4]); client = redis.Redis(host=host, port=port, password=password, db=db, socket_connect_timeout=2, socket_timeout=2); raise SystemExit(0 if client.ping() else 1)' \
    "${REDIS_HOST}" "${REDIS_PORT}" "${REDIS_PASSWORD}" "${REDIS_DB}" >/dev/null 2>&1
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
  echo "Redis is not reachable at ${REDIS_HOST}:${REDIS_PORT}; starting the local Docker Compose redis service..."

  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed or not on PATH. Start Redis manually, then rerun this script." >&2
    exit 1
  fi

  docker compose -f "${COMPOSE_FILE}" up -d redis

  if ! wait_for_redis 60; then
    echo "Redis did not become ready at ${REDIS_HOST}:${REDIS_PORT}. Check: docker compose -f ${COMPOSE_FILE} logs redis" >&2
    exit 1
  fi
fi

echo "Redis is ready at ${REDIS_HOST}:${REDIS_PORT}."

cd "${BACKEND_DIR}"
exec env TRADING_AGENTS_LOG_DIR=../runtime/logs PYTHONPATH=. \
  conda run -n trader python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
