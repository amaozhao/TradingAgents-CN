from types import SimpleNamespace

import pytest

from app.routers.config import setup


@pytest.mark.asyncio
async def test_reload_config_uses_async_bridge_reload(monkeypatch):
    calls: list[str] = []

    async def async_reload():
        calls.append("async")
        return True

    async def fake_log_operation(**_kwargs):
        return None

    def fake_import(name: str):
        if name == "app.core.bridge":
            return SimpleNamespace(
                reload_bridged_config=lambda: (_ for _ in ()).throw(
                    AssertionError("reload_config must use async bridge reload")
                ),
                reload_bridged_config_async=async_reload,
            )
        return setup.importlib.import_module(name)

    monkeypatch.setattr(setup.importlib, "import_module", fake_import)
    monkeypatch.setattr(setup, "log_operation", fake_log_operation)

    response = await setup.reload_config({"user_id": "u1", "username": "admin"})

    assert calls == ["async"]
    assert response["success"] is True
