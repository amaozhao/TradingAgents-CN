import re
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic

from .baseclient import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatAnthropic(ChatAnthropic):
    """Anthropic wrapper that normalizes structured content to text."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    @staticmethod
    def _supports_effort(model: str) -> bool:
        normalized = str(model).lower()
        if "haiku" in normalized:
            return False
        if "mythos" in normalized:
            return True
        return bool(re.match(r"^claude-(opus|sonnet)-\d+-\d+", normalized))

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in (
            "timeout",
            "max_retries",
            "callbacks",
            "http_client",
            "http_async_client",
            "temperature",
            "max_tokens",
        ):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        if "effort" in self.kwargs and self._supports_effort(self.model):
            llm_kwargs["effort"] = self.kwargs["effort"]

        api_key = self.kwargs.get("api_key")
        if api_key:
            llm_kwargs["api_key"] = api_key

        return NormalizedChatAnthropic(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("anthropic", self.model)
