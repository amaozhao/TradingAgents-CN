from scripts import postgres_api_smoke as smoke


def test_extract_token_supports_wrapped_login_response():
    payload = {"success": True, "data": {"access_token": "token-1"}}

    assert smoke._extract_token(payload) == "token-1"


def test_is_empty_data_checks_wrapped_data_without_unhashable_errors():
    assert smoke._is_empty_data({"success": True, "data": []}) is True
    assert smoke._is_empty_data({"success": True, "data": {}}) is True
    assert smoke._is_empty_data({"success": True, "data": {"items": []}}) is False
    assert smoke._is_empty_data({"status": "ok"}) is False


def test_build_checks_fails_auth_required_checks_without_auth_by_default():
    checks = smoke._build_checks(auth_available=False, allow_missing_auth=False)

    auth_me = next(check for check in checks if check.name == "auth_me")

    assert auth_me.auth_required is True
    assert auth_me.optional is False
    assert auth_me.skip_reason is None


def test_build_checks_can_skip_auth_required_checks_for_public_preflight():
    checks = smoke._build_checks(auth_available=False, allow_missing_auth=True)

    auth_me = next(check for check in checks if check.name == "auth_me")

    assert auth_me.auth_required is True
    assert auth_me.optional is True
    assert "missing authentication" in auth_me.skip_reason


def test_run_check_reports_success_false_as_failure(monkeypatch):
    client = smoke.ApiClient("http://example.test", token=None, timeout=1)

    def fake_request(*_args, **_kwargs):
        return 200, {"success": False, "data": {"error": "bad"}}

    monkeypatch.setattr(client, "request", fake_request)

    result = smoke._run_check(client, smoke.ApiCheck("x", "GET", "/x"))

    assert result.status == "failed"
    assert result.detail == "response success=false"


def test_build_checks_adds_migration_state_when_expected_flags_are_set(monkeypatch):
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_READ_ENABLED", "false")
    monkeypatch.setenv("TRADING_AGENTS_EXPECT_POSTGRES_DUAL_WRITE_ENABLED", "true")

    checks = smoke._build_checks(auth_available=True, allow_missing_auth=False)
    migration_state = next(check for check in checks if check.name == "migration_state")

    assert migration_state.path == "/api/system/config/summary"
    assert migration_state.auth_required is True
    assert migration_state.expected_settings == {
        "POSTGRES_READ_ENABLED": False,
        "POSTGRES_DUAL_WRITE_ENABLED": True,
    }


def test_run_check_validates_expected_migration_settings(monkeypatch):
    client = smoke.ApiClient("http://example.test", token="token", timeout=1)

    def fake_request(*_args, **_kwargs):
        return 200, {
            "settings": {
                "POSTGRES_READ_ENABLED": False,
                "POSTGRES_DUAL_WRITE_ENABLED": True,
            }
        }

    monkeypatch.setattr(client, "request", fake_request)

    passed = smoke._run_check(
        client,
        smoke.ApiCheck(
            "migration_state",
            "GET",
            "/api/system/config/summary",
            auth_required=True,
            require_success_field=False,
            expected_settings={
                "POSTGRES_READ_ENABLED": False,
                "POSTGRES_DUAL_WRITE_ENABLED": True,
            },
        ),
    )
    failed = smoke._run_check(
        client,
        smoke.ApiCheck(
            "migration_state",
            "GET",
            "/api/system/config/summary",
            auth_required=True,
            require_success_field=False,
            expected_settings={"POSTGRES_READ_ENABLED": True},
        ),
    )

    assert passed.status == "passed"
    assert failed.status == "failed"
    assert "POSTGRES_READ_ENABLED" in failed.detail
