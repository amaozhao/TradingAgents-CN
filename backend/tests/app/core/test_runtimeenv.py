from app.core.runtimeenv import apply_runtime_env


def test_apply_runtime_env_skips_empty_values():
    environ = {}

    applied = apply_runtime_env({"HTTP_PROXY": "", "NO_PROXY": "localhost"}, environ=environ)

    assert applied == {"NO_PROXY": "localhost"}
    assert environ == {"NO_PROXY": "localhost"}


def test_apply_runtime_env_can_preserve_existing_values():
    environ = {"HTTP_PROXY": "http://existing"}

    applied = apply_runtime_env(
        {"HTTP_PROXY": "http://new", "HTTPS_PROXY": "http://secure"},
        environ=environ,
        overwrite=False,
    )

    assert applied == {"HTTPS_PROXY": "http://secure"}
    assert environ == {"HTTP_PROXY": "http://existing", "HTTPS_PROXY": "http://secure"}
