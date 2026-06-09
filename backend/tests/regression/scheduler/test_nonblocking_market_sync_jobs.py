import inspect
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_market_sync_scheduler_wrappers_run_as_executor_jobs():
    setup_path = Path(__file__).resolve().parents[3] / "app" / "main" / "setup.py"
    spec = spec_from_file_location("app_main_setup_under_test", setup_path)
    assert spec is not None and spec.loader is not None
    setup = module_from_spec(spec)
    spec.loader.exec_module(setup)

    wrappers = [
        setup.run_tushare_quotes_sync,
        setup.run_tushare_historical_sync,
        setup.run_akshare_basic_info_sync,
        setup.run_akshare_historical_sync,
        setup.run_baostock_daily_quotes_sync,
        setup.run_baostock_historical_sync,
    ]

    assert all(not inspect.iscoroutinefunction(wrapper) for wrapper in wrappers)
