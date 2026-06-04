from pathlib import Path


def test_favorites_router_does_not_use_dict_response_model():
    router_path = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "favorites.py"
    )

    assert "response_model=dict" not in router_path.read_text(encoding="utf-8")
