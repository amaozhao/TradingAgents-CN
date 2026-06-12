from __future__ import annotations

from app.services.research.agent.runtime import direct_tool_call_from_metadata


def test_direct_tool_call_from_metadata_accepts_batch_stock_analysis() -> None:
    result = direct_tool_call_from_metadata(
        {
            "tool_name": "batch_stock_analysis",
            "tool_arguments": {
                "title": "测试",
                "symbols": ["000001", "600519"],
                "market_type": "A",
            },
        }
    )

    assert result == {
        "tool_name": "batch_stock_analysis",
        "tool_arguments": {
            "title": "测试",
            "symbols": ["000001", "600519"],
            "market_type": "A",
        },
    }


def test_direct_tool_call_from_metadata_rejects_batch_without_symbols() -> None:
    result = direct_tool_call_from_metadata(
        {
            "tool_name": "batch_stock_analysis",
            "tool_arguments": {
                "title": "测试",
                "market_type": "A",
            },
        }
    )

    assert result is None
