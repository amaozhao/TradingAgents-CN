from __future__ import annotations

from app.routers import screening


def test_build_industries_merges_fallback_sources_when_preferred_is_empty():
    documents = [
        {"code": "600519", "source": "akshare", "industry": ""},
        {"code": "000001", "source": "akshare", "industry": None},
        {"code": "600519", "source": "baostock", "industry": "酒、饮料和精制茶制造业"},
        {"code": "000001", "source": "baostock", "industry": "货币金融服务"},
        {"code": "600000", "source": "baostock", "industry": "货币金融服务"},
    ]

    industries, source = screening._build_industry_options_from_documents(
        documents, ["akshare", "baostock"]
    )

    assert source == "baostock"
    assert industries == [
        {"value": "货币金融服务", "label": "货币金融服务", "count": 2},
        {
            "value": "酒、饮料和精制茶制造业",
            "label": "酒、饮料和精制茶制造业",
            "count": 1,
        },
    ]


def test_build_industries_keeps_preferred_source_when_it_has_values():
    documents = [
        {"code": "600519", "source": "akshare", "industry": "白酒"},
        {"code": "000001", "source": "baostock", "industry": "货币金融服务"},
    ]

    industries, source = screening._build_industry_options_from_documents(
        documents, ["akshare", "baostock"]
    )

    assert source == "akshare"
    assert industries == [{"value": "白酒", "label": "白酒", "count": 1}]
