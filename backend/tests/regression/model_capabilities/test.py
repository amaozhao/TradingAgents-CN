from app.constants.capabilities import ModelFeature
from app.services.capability import ModelCapabilityService


def test_minimax_empty_database_features_fall_back_to_default_capabilities(
    monkeypatch,
):
    from app.core import database

    class Collection:
        def find_one(self, _query, sort=None):
            return {
                "is_active": True,
                "version": 1,
                "llm_configs": [
                    {
                        "model_name": "MiniMax-M3",
                        "capability_level": 2,
                        "suitable_roles": ["both"],
                        "features": [],
                        "recommended_depths": ["快速", "基础", "标准"],
                    }
                ],
            }

    class Db:
        system_configs = Collection()

    monkeypatch.setattr(database, "get_postgres_db_sync", lambda: Db())

    service = ModelCapabilityService()
    model_config = service.get_model_config("MiniMax-M3")
    validation = service.validate_model_pair("MiniMax-M3", "MiniMax-M3", "标准")

    assert ModelFeature.TOOL_CALLING in model_config["features"]
    assert validation["valid"] is True
