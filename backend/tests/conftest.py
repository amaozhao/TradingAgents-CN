import os
import sys
import types
import asyncio
import inspect
import pytest

# 将仓库根目录和 backend 源码目录加入 sys.path，确保迁移后仍可使用
# 原有的 `import app` / `import trader` 包名。
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-api-key")
os.environ.setdefault("MONGODB_HOST", "localhost")
os.environ.setdefault("MONGODB_PORT", "27017")
os.environ.setdefault("MONGODB_DATABASE", "trading_agents_cn")
os.environ.setdefault("MONGODB_USERNAME", "admin")
os.environ.setdefault("MONGODB_PASSWORD", "trading_agents123")
os.environ.setdefault("MONGODB_AUTH_SOURCE", "admin")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("JWT_SECRET", "change-me-in-production")

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
    if os.getenv("TRADING_AGENTS_RUN_LIVE_TESTS"):
        return

    live_files = {
        "test_analysis_result.py",
        "test_async_analysis.py",
        "test_decision_data.py",
        "test_existing_results.py",
        "test_fundamentals_no_duplicate.py",
        "test_industries_api.py",
        "test_industry_screening_fix.py",
        "test_non_blocking.py",
        "test_real_estate_api.py",
        "test_reports_api.py",
        "test_summary_recommendation.py",
    }
    helper_files = {
        "test_conversion.py",
        "test_market_analyst_lookback.py",
        "test_real_data_levels.py",
        "test_sanitize_real_data.py",
        "test_simple_depth_check.py",
    }
    skip_live = pytest.mark.skip(reason="requires a running local backend; set TRADING_AGENTS_RUN_LIVE_TESTS=1 to run")
    skip_helper = pytest.mark.skip(reason="script helper, not a standalone pytest test")

    for item in items:
        path = getattr(item, "path", None)
        filename = path.name if path is not None else os.path.basename(str(getattr(item, "fspath", "")))
        if filename in live_files:
            item.add_marker(skip_live)
        elif filename in helper_files:
            item.add_marker(skip_helper)
        elif filename == "test_quotes_ingestion.py" and item.name in {
            "test_market_quotes_status",
            "test_historical_data_import",
        }:
            item.add_marker(skip_live)
        elif filename == "test_akshare_hk_apis.py" and item.name == "test_api":
            item.add_marker(skip_helper)
