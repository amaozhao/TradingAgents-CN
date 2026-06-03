from pathlib import Path


def test_model_capabilities_router_does_not_use_dict_response_model():
    router_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "model_capabilities.py"

    assert "response_model=dict" not in router_path.read_text(encoding="utf-8")
