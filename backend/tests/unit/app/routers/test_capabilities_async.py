import pytest

from app.routers import capabilities
from app.routers.capabilities import ModelValidationRequest


class AsyncCapabilityService:
    def validate_model_pair(self, *_args):
        raise AssertionError("sync capability validation must not be used")

    async def validate_model_pair_async(self, *_args):
        return {"valid": True, "warnings": [], "recommendations": []}


@pytest.mark.asyncio
async def test_validate_models_uses_async_capability_service(monkeypatch):
    monkeypatch.setattr(
        capabilities,
        "get_model_capability_service",
        lambda: AsyncCapabilityService(),
    )

    response = await capabilities.validate_models(
        ModelValidationRequest(
            quick_model="qwen-turbo",
            deep_model="qwen-plus",
            research_depth="标准",
        )
    )

    assert response["success"] is True
    assert response["data"]["valid"] is True
