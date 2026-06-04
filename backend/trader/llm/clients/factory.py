import importlib
from typing import Optional

from .base import BaseLLMClient
from .providers import normalize_provider_key

_PROVIDER_ALIASES = {
    "dashscope": "qwen",
    "alibaba": "qwen",
    "zhipu": "glm",
    "siliconflow": "openai",
}

_OPENAI_COMPATIBLE = {
    "openai",
    "azure",
    "xai",
    "deepseek",
    "qwen",
    "qwen-cn",
    "glm",
    "glm-cn",
    "minimax",
    "minimax-cn",
    "qianfan",
    "openrouter",
    "aihubmix",
    "ollama",
    "custom_openai",
}


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    provider_lower = normalize_provider_key(provider)
    provider_lower = _PROVIDER_ALIASES.get(provider_lower, provider_lower)

    if provider_lower in _OPENAI_COMPATIBLE:
        if provider_lower == "azure":
            AzureOpenAIClient = getattr(
                importlib.import_module("trader.llm.clients.azure"), "AzureOpenAIClient"
            )

            return AzureOpenAIClient(model, base_url, **kwargs)

        OpenAIClient = getattr(
            importlib.import_module("trader.llm.clients.openai"), "OpenAIClient"
        )

        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    if provider_lower == "google":
        GoogleClient = getattr(
            importlib.import_module("trader.llm.clients.google"), "GoogleClient"
        )

        return GoogleClient(model, base_url, **kwargs)

    if provider_lower in {"anthropic", "minimax-token-plan"}:
        AnthropicClient = getattr(
            importlib.import_module("trader.llm.clients.anthropic"), "AnthropicClient"
        )

        return AnthropicClient(model, base_url, provider=provider_lower, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
