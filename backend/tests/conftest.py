import asyncio
import importlib
import inspect
import os
import sys
import types

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS_TRADER_ROOT = os.path.join(os.path.dirname(__file__), "trader")

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


def _module_origin_is_under(module, root: str) -> bool:
    module_file = getattr(module, "__file__", None)
    if module_file and os.path.abspath(module_file).startswith(root):
        return True
    try:
        module_paths = getattr(module, "__path__", None) or []
        module_paths = list(module_paths)
    except KeyError:
        return True
    return any(os.path.abspath(path).startswith(root) for path in module_paths)


def _clear_test_trader_namespace() -> None:
    loaded_modules = sorted(
        list(sys.modules.items()),
        key=lambda item: item[0].count("."),
        reverse=True,
    )
    for module_name, module in loaded_modules:
        if module_name == "trader" or module_name.startswith("trader."):
            if module is not None and _module_origin_is_under(module, TESTS_TRADER_ROOT):
                sys.modules.pop(module_name, None)


_clear_test_trader_namespace()

app_settings = importlib.import_module("app.core.config").settings
apply_runtime_env = importlib.import_module("app.core.runtime").apply_runtime_env

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


def pytest_collection_finish(session):
    _clear_test_trader_namespace()


def pytest_runtest_setup(item):
    _clear_test_trader_namespace()


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
