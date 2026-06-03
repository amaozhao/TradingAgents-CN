from pathlib import Path

from app.routers.configrouter import ConfigApiResponse


def test_config_router_does_not_use_dict_response_model():
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "config.py"

    assert "response_model=dict" not in router_path.read_text(encoding="utf-8")


def test_config_api_response_preserves_extra_settings_fields():
    response = ConfigApiResponse(
        success=True,
        data={"timezone": "Asia/Shanghai"},
        message="ok",
        timezone="Asia/Shanghai",
    )

    assert response.model_dump()["timezone"] == "Asia/Shanghai"
