from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 15


@dataclass
class ApiCheck:
    name: str
    method: str
    path: str
    auth_required: bool = False
    body: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    require_success_field: bool = True
    require_data: bool = False
    optional: bool = False
    skip_reason: str | None = None
    expected_settings: dict[str, Any] | None = None


@dataclass
class ApiCheckResult:
    name: str
    status: str
    detail: str
    method: str
    path: str
    status_code: int | None = None
    sample: Any = None


class ApiClient:
    def __init__(self, base_url: str, *, token: str | None, timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> tuple[int, Any]:
        query = ""
        if params:
            query = "?" + urlencode(
                {key: value for key, value in params.items() if value is not None},
                doseq=True,
            )
        url = f"{self.base_url}{path}{query}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
                return response.status, _decode_json(payload)
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            return exc.code, _decode_json(payload)
        except URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc


def run_api_smoke(
    *,
    base_url: str,
    token: str | None,
    username: str | None,
    password: str | None,
    timeout: int,
    allow_missing_auth: bool,
) -> dict[str, Any]:
    client = ApiClient(base_url, token=token, timeout=timeout)
    auth_detail = "token"
    if not token and username and password:
        login_status, login_payload = client.request(
            "POST",
            "/api/auth/login",
            body={"username": username, "password": password},
        )
        token = _extract_token(login_payload)
        client.token = token
        auth_detail = "login"
        if login_status >= 400 or not token:
            return {
                "all_passed": False,
                "base_url": base_url,
                "auth": {"mode": auth_detail, "authenticated": False},
                "checks": [
                    asdict(
                        ApiCheckResult(
                            name="auth_login",
                            status="failed",
                            detail=f"login failed with status {login_status}",
                            method="POST",
                            path="/api/auth/login",
                            status_code=login_status,
                            sample=login_payload,
                        )
                    )
                ],
            }

    checks = _build_checks(
        auth_available=bool(token), allow_missing_auth=allow_missing_auth
    )
    results = [_run_check(client, check) for check in checks]
    return {
        "all_passed": all(result.status != "failed" for result in results),
        "base_url": base_url,
        "auth": {
            "mode": auth_detail if token else "missing",
            "authenticated": bool(token),
        },
        "checks": [asdict(result) for result in results],
    }


def _build_checks(*, auth_available: bool, allow_missing_auth: bool) -> list[ApiCheck]:
    stock_code = os.getenv("TRADING_AGENTS_SMOKE_STOCK_CODE", "000001")
    symbol = os.getenv("TRADING_AGENTS_SMOKE_SYMBOL", stock_code)
    search_query = os.getenv("TRADING_AGENTS_SMOKE_SEARCH_QUERY", stock_code)
    task_id = os.getenv("TRADING_AGENTS_SMOKE_TASK_ID")
    expected_migration_settings = _expected_migration_settings()

    auth_skip = None
    if not auth_available:
        auth_skip = "missing authentication; provide TRADING_AGENTS_API_TOKEN or username/password"

    def auth_check(**kwargs) -> ApiCheck:
        if auth_skip and allow_missing_auth:
            return ApiCheck(
                **kwargs, auth_required=True, optional=True, skip_reason=auth_skip
            )
        return ApiCheck(**kwargs, auth_required=True)

    checks = [
        ApiCheck("health", "GET", "/api/health", require_data=True),
        ApiCheck("readyz", "GET", "/api/readyz", require_success_field=False),
        ApiCheck(
            "financial_data",
            "GET",
            f"/api/financial-data/query/{stock_code}",
            params={"limit": 1},
            require_data=True,
        ),
        ApiCheck(
            "internal_messages_health",
            "GET",
            "/api/internal-messages/health",
            require_data=False,
        ),
        ApiCheck(
            "internal_messages_query",
            "POST",
            "/api/internal-messages/query",
            body={"symbol": symbol, "limit": 5},
            require_data=True,
        ),
        ApiCheck(
            "internal_messages_search",
            "GET",
            "/api/internal-messages/search",
            params={"query": search_query, "symbol": symbol, "limit": 5},
            require_data=True,
        ),
        ApiCheck(
            "internal_messages_stats",
            "GET",
            "/api/internal-messages/statistics",
            params={"symbol": symbol, "hours_back": 168},
            require_data=True,
        ),
        ApiCheck(
            "social_media_health", "GET", "/api/social-media/health", require_data=False
        ),
        ApiCheck(
            "social_media_query",
            "POST",
            "/api/social-media/query",
            body={"symbol": symbol, "limit": 5},
            require_data=True,
        ),
        ApiCheck(
            "social_media_search",
            "GET",
            "/api/social-media/search",
            params={"query": search_query, "symbol": symbol, "limit": 5},
            require_data=True,
        ),
        ApiCheck(
            "social_media_stats",
            "GET",
            "/api/social-media/statistics",
            params={"symbol": symbol, "hours_back": 168},
            require_data=True,
        ),
        ApiCheck(
            "model_capabilities",
            "GET",
            "/api/model-capabilities/default-configs",
            require_data=True,
        ),
        auth_check(
            name="auth_me", method="GET", path="/api/auth/me", require_data=True
        ),
        auth_check(
            name="stock_quote",
            method="GET",
            path=f"/api/stocks/{stock_code}/quote",
            require_data=True,
        ),
        auth_check(
            name="stock_fundamentals",
            method="GET",
            path=f"/api/stocks/{stock_code}/fundamentals",
            require_data=True,
        ),
        auth_check(
            name="stock_search",
            method="GET",
            path="/api/markets/CN/stocks/search",
            params={"q": stock_code, "limit": 5},
            require_data=True,
        ),
        auth_check(
            name="market_stock_info",
            method="GET",
            path=f"/api/markets/CN/stocks/{stock_code}/info",
            require_data=True,
        ),
        auth_check(
            name="daily_quotes",
            method="GET",
            path=f"/api/markets/CN/stocks/{stock_code}/daily",
            params={"limit": 5},
            require_data=True,
        ),
        auth_check(
            name="favorites", method="GET", path="/api/favorites/", require_data=False
        ),
        auth_check(name="tags", method="GET", path="/api/tags/", require_data=False),
        auth_check(
            name="paper_account",
            method="GET",
            path="/api/paper/account",
            require_data=True,
        ),
        auth_check(
            name="operation_logs",
            method="GET",
            path="/api/system/logs/list",
            params={"page": 1, "page_size": 5},
            require_data=True,
        ),
        auth_check(
            name="operation_log_stats",
            method="GET",
            path="/api/system/logs/stats",
            require_data=True,
        ),
        auth_check(
            name="news_query",
            method="GET",
            path=f"/api/news-data/query/{symbol}",
            params={"limit": 5, "hours_back": 87600},
            require_data=True,
        ),
        auth_check(
            name="config_system",
            method="GET",
            path="/api/config/system",
            require_data=True,
        ),
    ]
    if expected_migration_settings:
        checks.append(
            auth_check(
                name="migration_state",
                method="GET",
                path="/api/system/config/summary",
                require_success_field=False,
                expected_settings=expected_migration_settings,
            )
        )
    if task_id:
        checks.append(
            auth_check(
                name="analysis_task_status",
                method="GET",
                path=f"/api/analysis/tasks/{task_id}/status",
                require_data=True,
            )
        )
        checks.append(
            auth_check(
                name="analysis_task_result",
                method="GET",
                path=f"/api/analysis/tasks/{task_id}/result",
                require_data=True,
            )
        )
    else:
        checks.append(
            ApiCheck(
                name="analysis_task_status",
                method="GET",
                path="/api/analysis/tasks/{task_id}/status",
                optional=True,
                skip_reason="TRADING_AGENTS_SMOKE_TASK_ID is not set",
            )
        )
    return checks


def _run_check(client: ApiClient, check: ApiCheck) -> ApiCheckResult:
    if check.optional and check.skip_reason:
        return ApiCheckResult(
            name=check.name,
            status="skipped",
            detail=check.skip_reason,
            method=check.method,
            path=check.path,
        )
    if check.auth_required and not client.token:
        return ApiCheckResult(
            name=check.name,
            status="failed",
            detail="authentication is required",
            method=check.method,
            path=check.path,
        )

    try:
        status_code, payload = client.request(
            check.method,
            check.path,
            body=check.body,
            params=check.params,
            auth=check.auth_required,
        )
    except Exception as exc:
        return ApiCheckResult(
            name=check.name,
            status="failed",
            detail=str(exc),
            method=check.method,
            path=check.path,
        )

    if status_code < 200 or status_code >= 300:
        return ApiCheckResult(
            name=check.name,
            status="failed",
            detail=f"unexpected HTTP status {status_code}",
            method=check.method,
            path=check.path,
            status_code=status_code,
            sample=payload,
        )
    if (
        check.require_success_field
        and isinstance(payload, dict)
        and payload.get("success") is False
    ):
        return ApiCheckResult(
            name=check.name,
            status="failed",
            detail="response success=false",
            method=check.method,
            path=check.path,
            status_code=status_code,
            sample=payload,
        )
    if check.require_data and _is_empty_data(payload):
        return ApiCheckResult(
            name=check.name,
            status="failed",
            detail="response data is empty",
            method=check.method,
            path=check.path,
            status_code=status_code,
            sample=payload,
        )
    if check.expected_settings:
        mismatch = _settings_mismatch(payload, check.expected_settings)
        if mismatch:
            return ApiCheckResult(
                name=check.name,
                status="failed",
                detail=mismatch,
                method=check.method,
                path=check.path,
                status_code=status_code,
                sample=_sample_payload(payload),
            )
    return ApiCheckResult(
        name=check.name,
        status="passed",
        detail="ok",
        method=check.method,
        path=check.path,
        status_code=status_code,
        sample=_sample_payload(payload),
    )


def _extract_token(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        token = data.get("access_token")
        if token:
            return str(token)
    token = payload.get("access_token")
    return str(token) if token else None


def _expected_migration_settings() -> dict[str, bool]:
    expected: dict[str, bool] = {}
    for env_name, setting_name in (
        ("TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED", "POSTGRES_READ_ENABLED"),
        (
            "TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED",
            "POSTGRES_DUAL_WRITE_ENABLED",
        ),
    ):
        raw = os.getenv(env_name)
        if raw is not None:
            expected[setting_name] = _parse_bool(raw)
    return expected


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _settings_mismatch(payload: Any, expected_settings: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return "response is not a JSON object"
    settings_payload = payload.get("settings")
    if not isinstance(settings_payload, dict):
        return "response does not contain settings object"
    mismatches = []
    for key, expected in expected_settings.items():
        actual = settings_payload.get(key)
        if actual != expected:
            mismatches.append(f"{key}: expected {expected!r}, got {actual!r}")
    if mismatches:
        return "; ".join(mismatches)
    return None


def _is_empty_data(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return payload is None or payload == "" or payload == [] or payload == {}
    if "data" not in payload:
        return False
    data = payload.get("data")
    return data is None or data == "" or data == [] or data == {}


def _sample_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        sample = dict(payload)
        if isinstance(sample.get("data"), list):
            sample["data"] = {
                "list_length": len(sample["data"]),
                "first": sample["data"][0] if sample["data"] else None,
            }
        if isinstance(sample.get("data"), dict):
            data = sample["data"]
            sample["data"] = {
                "keys": sorted(data.keys())[:20],
                "size": len(data),
            }
        return sample
    return payload


def _decode_json(payload: str) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload[:1000]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test deployed TradingAgents API after PostgreSQL read cutover."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("TRADING_AGENTS_API_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--token", default=os.getenv("TRADING_AGENTS_API_TOKEN"))
    parser.add_argument("--username", default=os.getenv("TRADING_AGENTS_API_USERNAME"))
    parser.add_argument("--password", default=os.getenv("TRADING_AGENTS_API_PASSWORD"))
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("TRADING_AGENTS_API_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
    )
    parser.add_argument("--allow-missing-auth", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = run_api_smoke(
        base_url=args.base_url,
        token=args.token,
        username=args.username,
        password=args.password,
        timeout=args.timeout,
        allow_missing_auth=args.allow_missing_auth,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
