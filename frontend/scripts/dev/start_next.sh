#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${FRONTEND_DIR}"

export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:8000}"

# The local frontend proxies only to the local backend. Do not inherit user-level
# proxy settings here; they can make Next's development proxy return 500s.
for key in \
  HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy \
  WS_PROXY WSS_PROXY ws_proxy wss_proxy \
  NPM_CONFIG_PROXY NPM_CONFIG_HTTP_PROXY NPM_CONFIG_HTTPS_PROXY \
  npm_config_proxy npm_config_http_proxy npm_config_https_proxy
do
  unset "${key}"
done

export NO_PROXY="127.0.0.1,localhost,::1"
export no_proxy="${NO_PROXY}"

exec pnpm dev --hostname 127.0.0.1 --port 3000
