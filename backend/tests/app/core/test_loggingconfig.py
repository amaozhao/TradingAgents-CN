import os
from importlib import reload
from pathlib import Path

import pytest


MINIMAL_TOML = """
[logging]
level = "INFO"

[logging.format]
console = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
file = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

[logging.handlers.file]
directory = "./logs"
level = "DEBUG"
max_size = "1MB"
backup_count = 1
"""


@pytest.mark.parametrize("profile, expect_name", [
    ("", "logging.toml"),
    ("docker", "logging_docker.toml"),
])
def test_logging_uses_expected_toml(profile, expect_name, monkeypatch, tmp_path, caplog):
    # Arrange: create temporary config directory with desired files
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    # default config
    (cfg_dir / "logging.toml").write_text(MINIMAL_TOML, encoding="utf-8")
    # docker config (only when needed)
    (cfg_dir / "logging_docker.toml").write_text(MINIMAL_TOML, encoding="utf-8")

    # Switch CWD to the temp project root
    monkeypatch.chdir(tmp_path)

    # Clear/set env
    if profile:
        monkeypatch.setenv("LOGGING_PROFILE", profile)
    else:
        monkeypatch.delenv("LOGGING_PROFILE", raising=False)
        monkeypatch.delenv("DOCKER", raising=False)

    # Import after chdir to ensure relative paths resolve under tmp_path
    from app.core import loggingconfig as lc
    reload(lc)

    # Act: resolve which file will be used, then apply logging
    chosen = lc.resolve_logging_cfg_path()
    assert chosen.name == expect_name
    lc.setup_logging("INFO")


from testsupport.registry import export_module as _export_module
_export_module(globals(), "testsupport.testsxconfigxtestloggingjson")
_export_module(globals(), "testsupport.testsxdebugaksharedailybasic")
_export_module(globals(), "testsupport.testsxdebugbaostockfields")
_export_module(globals(), "testsupport.testsxdebugbaostockstocklist")
_export_module(globals(), "testsupport.testsxtestaksharealternative")
_export_module(globals(), "testsupport.testsxtestakshareapi")
_export_module(globals(), "testsupport.testsxtestaksharefixed")
_export_module(globals(), "testsupport.testsxtestakshareperformance")
_export_module(globals(), "testsupport.testsxtestapperrorlogging")
_export_module(globals(), "testsupport.testsxtestbaostockfixed")
_export_module(globals(), "testsupport.testsxtestbaostockstockfilter")
_export_module(globals(), "testsupport.testsxtestbaostockvaluation")
_export_module(globals(), "testsupport.testsxtestdashscopetoolcallfix")
_export_module(globals(), "testsupport.testsxtestwebapiakshare")
del _export_module
