from typing import Optional

from .baseclient import BaseLLMClient
from .providerkeys import normalize_provider_key


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
            from .azureclient import AzureOpenAIClient

            return AzureOpenAIClient(model, base_url, **kwargs)

        from .openaiclient import OpenAIClient

        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    if provider_lower == "google":
        from .googleclient import GoogleClient

        return GoogleClient(model, base_url, **kwargs)

    if provider_lower == "anthropic":
        from .anthropicclient import AnthropicClient

        return AnthropicClient(model, base_url, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
