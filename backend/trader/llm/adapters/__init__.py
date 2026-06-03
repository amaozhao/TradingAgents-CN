# LLM Adapters for TradingAgents
from .dashscope.openai import ChatDashScopeOpenAI
from .google.openai import ChatGoogleOpenAI

__all__ = ["ChatDashScopeOpenAI", "ChatGoogleOpenAI"]
