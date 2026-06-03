from typing import Any

from .baseclient import BaseLLMClient
from .validators import validate_model

try:
    from tradingagents.llmadapters.googleopenaiadapter import ChatGoogleOpenAI as NormalizedChatGoogleGenerativeAI
except Exception:
    NormalizedChatGoogleGenerativeAI = None


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models."""

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        chat_cls = NormalizedChatGoogleGenerativeAI
        if chat_cls is None:
            from tradingagents.llmadapters.googleopenaiadapter import ChatGoogleOpenAI as chat_cls

        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in (
            "temperature",
            "max_tokens",
            "timeout",
            "max_retries",
            "callbacks",
            "http_client",
            "http_async_client",
            "transport",
            "thinking_level",
        ):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        google_api_key = self.kwargs.get("api_key") or self.kwargs.get("google_api_key")
        if google_api_key:
            llm_kwargs["google_api_key"] = google_api_key

        return chat_cls(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("google", self.model)
