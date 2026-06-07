import asyncio
import inspect
import os
import sys
import types

import pytest
from app.core.config import settings as app_settings
from app.core.runtime import apply_runtime_env

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

apply_runtime_env(
    {
        "GOOGLE_API_KEY": app_settings.GOOGLE_API_KEY or "test-google-api-key",
        "OPENAI_API_KEY": app_settings.OPENAI_API_KEY or "test-openai-api-key",
        "POSTGRES_HOST": app_settings.POSTGRES_HOST,
        "POSTGRES_PORT": app_settings.POSTGRES_PORT,
        "POSTGRES_DB": app_settings.POSTGRES_DB,
        "POSTGRES_USER": app_settings.POSTGRES_USER,
        "POSTGRES_PASSWORD": app_settings.POSTGRES_PASSWORD,
        "REDIS_HOST": app_settings.REDIS_HOST,
        "REDIS_PORT": app_settings.REDIS_PORT,
        "JWT_SECRET": app_settings.JWT_SECRET,
    },
    overwrite=False,
)

# LangChain 1.x removed the old ``langchain.schema`` import path. Several
# legacy tests/scripts still import message classes there, so provide the
# compatibility module without shadowing the installed ``langchain`` package.
try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    schema_module = types.ModuleType("langchain.schema")
    setattr(schema_module, "AIMessage", AIMessage)
    setattr(schema_module, "HumanMessage", HumanMessage)
    setattr(schema_module, "SystemMessage", SystemMessage)
    sys.modules.setdefault("langchain.schema", schema_module)
except Exception:
    pass


def pytest_pyfunc_call(pyfuncitem):
    """Run legacy unmarked async test functions.

    Some older script-style tests define ``async def test_*`` without
    ``@pytest.mark.asyncio``. pytest-asyncio only owns marked tests in this
    environment, so keep those legacy tests executable.
    """
    test_func = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_func):
        return None

    funcargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
        if name in pyfuncitem.funcargs
    }
    asyncio.run(test_func(**funcargs))
    return True


def pytest_collection_modifyitems(config, items):
    helper_files = {
        "test_conversion.py",
        "test_market_analyst_lookback.py",
        "test_real_data_levels.py",
        "test_sanitize_real_data.py",
        "test_simple_depth_check.py",
    }
    skip_helper = pytest.mark.skip(reason="script helper, not a standalone pytest test")

    for item in items:
        path = getattr(item, "path", None)
        filename = (
            path.name
            if path is not None
            else os.path.basename(str(getattr(item, "fspath", "")))
        )
        if filename in helper_files:
            item.add_marker(skip_helper)
        elif filename == "test_akshare_hk_apis.py" and item.name == "test_api":
            item.add_marker(skip_helper)
