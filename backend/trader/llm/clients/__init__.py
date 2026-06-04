import importlib

from .base import BaseLLMClient, normalize_content


def create_llm_client(*args, **kwargs):
    _create_llm_client = getattr(
        importlib.import_module("trader.llm.clients.factory"), "create_llm_client"
    )

    return _create_llm_client(*args, **kwargs)


__all__ = ["BaseLLMClient", "create_llm_client", "normalize_content"]
