#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/docker/compose/docker-compose.yml"

cd "${REPO_ROOT}"
mkdir -p runtime/logs runtime/data

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  echo "backend/.env is required. Copy backend/.env.example to backend/.env and configure it first." >&2
  exit 1
fi

echo "Using backend environment from ${BACKEND_DIR}/.env."

CONDA_BIN="${CONDA_BIN:-$(command -v conda || true)}"
if [[ -z "${CONDA_BIN}" ]]; then
  echo "conda is not installed or not on PATH. Set CONDA_BIN to the conda executable path." >&2
  exit 1
fi

TRADING_AGENTS_PROXY_HOST="${TRADING_AGENTS_PROXY_HOST:-127.0.0.1}"
TRADING_AGENTS_PROXY_PORT="${TRADING_AGENTS_PROXY_PORT:-7897}"
TRADING_AGENTS_PROXY_URL="${TRADING_AGENTS_PROXY_URL:-http://${TRADING_AGENTS_PROXY_HOST}:${TRADING_AGENTS_PROXY_PORT}}"
BASE_NO_PROXY="${NO_PROXY:-${CLASH_NO_PROXY:-localhost,127.0.0.1,::1,*.local,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}}"
A_SHARE_NO_PROXY="eastmoney.com,.eastmoney.com,push2.eastmoney.com,push2his.eastmoney.com,82.push2.eastmoney.com,82.push2delay.eastmoney.com,gtimg.cn,.gtimg.cn,sina.com.cn,.sina.com.cn,api.tushare.pro,tushare.pro,.tushare.pro,waditu.com,.waditu.com,baostock.com,.baostock.com,www.baostock.com"
DIRECT_LLM_NO_PROXY="api.minimaxi.com,platform.minimaxi.com,minimaxi.com,.minimaxi.com,api.deepseek.com,platform.deepseek.com,deepseek.com,.deepseek.com"
PROJECT_DIRECT_HOSTS="${TRADING_AGENTS_DIRECT_HOSTS:-}"

export CLASH_PROXY_HOST="${TRADING_AGENTS_PROXY_HOST}"
export CLASH_MIXED_PORT="${TRADING_AGENTS_PROXY_PORT}"
export http_proxy="${TRADING_AGENTS_PROXY_URL}"
export https_proxy="${TRADING_AGENTS_PROXY_URL}"
export all_proxy="${TRADING_AGENTS_PROXY_URL}"
export HTTP_PROXY="${TRADING_AGENTS_PROXY_URL}"
export HTTPS_PROXY="${TRADING_AGENTS_PROXY_URL}"
export ALL_PROXY="${TRADING_AGENTS_PROXY_URL}"
export ws_proxy="${TRADING_AGENTS_PROXY_URL}"
export wss_proxy="${TRADING_AGENTS_PROXY_URL}"
export WS_PROXY="${TRADING_AGENTS_PROXY_URL}"
export WSS_PROXY="${TRADING_AGENTS_PROXY_URL}"
if [[ -n "${PROJECT_DIRECT_HOSTS}" ]]; then
  export no_proxy="${BASE_NO_PROXY},${A_SHARE_NO_PROXY},${DIRECT_LLM_NO_PROXY},${PROJECT_DIRECT_HOSTS}"
else
  export no_proxy="${BASE_NO_PROXY},${A_SHARE_NO_PROXY},${DIRECT_LLM_NO_PROXY}"
fi
export NO_PROXY="${no_proxy}"
export CLASH_NO_PROXY="${no_proxy}"

echo "Backend outbound proxy: ${TRADING_AGENTS_PROXY_URL}"
echo "A-share data domains and direct LLM hosts are bypassed via NO_PROXY."

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    local redis_args
    redis_args="$(
      env PYTHONPATH="${BACKEND_DIR}" "${CONDA_BIN}" run --no-capture-output -n trader python -c '
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

  env PYTHONPATH="${BACKEND_DIR}" "${CONDA_BIN}" run --no-capture-output -n trader python -c '
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
  "${CONDA_BIN}" run --no-capture-output -n trader python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
