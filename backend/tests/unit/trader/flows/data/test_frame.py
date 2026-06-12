import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest import mock

import pandas as pd


def install_stub(module_name: str, **attributes) -> None:
    module = ModuleType(module_name)
    for name, value in attributes.items():
        setattr(module, name, value)
    sys.modules[module_name] = module


def load_frame_module():
    install_stub("trader.flows.akshare", get_akshare_provider=lambda: None)
    install_stub("trader.flows.sources", get_data_source_manager=lambda: None)
    install_stub(
        "trader.flows.providers.china.baostock", get_baostock_provider=lambda: None
    )
    install_stub("trader.flows.tushare", get_tushare_provider=lambda: None)

    module_path = (
        Path(__file__).resolve().parents[5] / "trader" / "flows" / "data" / "frame.py"
    )
    spec = importlib.util.spec_from_file_location(
        "flow_data_frame_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_unified_dataframe_prefers_tushare_then_akshare_then_baostock():
    frame = load_frame_module()

    # 模拟三个来源：tushare成功，后两个不应被调用
    with (
        mock.patch.object(frame, "get_tushare_adapter") as m_ts,
        mock.patch.object(frame, "get_akshare_provider") as m_ak,
        mock.patch.object(frame, "get_baostock_provider") as m_bs,
        mock.patch.object(frame, "get_data_source_manager") as m_dsm,
    ):
        df_ts = pd.DataFrame(
            {
                "Open": [1, 2],
                "High": [2, 3],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
                "Volume": [100, 200],
                "Amount": [150, 500],
                "trade_date": ["2024-01-01", "2024-01-02"],
            }
        )
        m_ts.return_value.get_stock_data.return_value = df_ts
        m_ak.return_value.get_stock_data.return_value = pd.DataFrame()
        m_bs.return_value.get_stock_data.return_value = pd.DataFrame()

        # 当前源为 tushare
        m_dsm.return_value.current_source.value = "tushare"
        m_dsm.return_value.available_sources = []

        df = frame.get_china_daily_df_unified("000001", "2024-01-01", "2024-01-31")
        assert not df.empty
        assert "close" in df.columns  # 已标准化
        assert df.shape[0] == 2


def test_unified_dataframe_fallback_to_baostock_when_others_fail():
    frame = load_frame_module()

    with (
        mock.patch.object(frame, "get_tushare_adapter") as m_ts,
        mock.patch.object(frame, "get_akshare_provider") as m_ak,
        mock.patch.object(frame, "get_baostock_provider") as m_bs,
        mock.patch.object(frame, "get_data_source_manager") as m_dsm,
    ):
        m_ts.return_value.get_stock_data.return_value = pd.DataFrame()
        m_ak.return_value.get_stock_data.return_value = pd.DataFrame()
        df_bs = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "code": ["sz.000001", "sz.000001"],
                "open": [1, 2],
                "high": [2, 3],
                "low": [0.5, 1.5],
                "close": [1.5, 2.5],
                "volume": [100, 200],
                "amount": [150, 500],
            }
        )
        m_bs.return_value.get_stock_data.return_value = df_bs

        m_dsm.return_value.current_source.value = "tushare"
        m_dsm.return_value.available_sources = ["akshare", "baostock"]

        df = frame.get_china_daily_df_unified("000001", "2024-01-01", "2024-01-31")
        assert not df.empty
        assert "close" in df.columns
        assert df.iloc[0]["close"] == 1.5
