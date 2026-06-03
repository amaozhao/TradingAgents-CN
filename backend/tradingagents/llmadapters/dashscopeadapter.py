"""Backward-compatible DashScope adapter import path."""

from tradingagents.llmadapters.dashscopeopenaiadapter import (
    ChatDashScopeOpenAI,
    create_dashscope_openai_llm,
    get_available_openai_models,
    test_dashscope_openai_connection,
    test_dashscope_openai_function_calling,
)

ChatDashScope = ChatDashScopeOpenAI

__all__ = [
    "ChatDashScope",
    "ChatDashScopeOpenAI",
    "create_dashscope_openai_llm",
    "get_available_openai_models",
    "test_dashscope_openai_connection",
    "test_dashscope_openai_function_calling",
]
