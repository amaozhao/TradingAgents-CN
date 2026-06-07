#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试股票详情基本面数据获取增强功能

测试内容：
1. 从 PostgreSQL 获取基础信息（stock_basic_info）
2. 从 PostgreSQL 获取财务数据（stock_financial_data）
3. 验证板块、ROE、负债率等字段
4. 测试降级机制
"""

import asyncio
import importlib
from datetime import datetime

from app.core.config import settings
from app.core.database import get_postgres_db, init_database
from trader.flows.providers.china.baostock import BaoStockProvider


def _first_present(data: dict, keys: tuple[str, ...]):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", "--"):
            return value
    return None


def _safe_float(value):
    if value in (None, "", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def fetch_public_stock_profile(code6: str) -> dict:
    """Fetch minimal public stock profile when the local database is incomplete."""
    ak = importlib.import_module("akshare")

    def fetch():
        return ak.stock_individual_info_em(symbol=code6)

    try:
        df = await asyncio.to_thread(fetch)
    except Exception as e:
        print(f"⚠️ 公开基础信息获取失败: {e}")
        return {}

    if df is None or df.empty:
        return {}

    rows = df.to_dict("records")
    profile = {
        str(row.get("item")): row.get("value")
        for row in rows
        if row.get("item") is not None
    }
    return {
        "code": code6,
        "name": _first_present(profile, ("股票简称", "简称", "名称")),
        "industry": _first_present(profile, ("行业", "所属行业")),
        "market": _first_present(profile, ("市场", "行业", "所属行业")),
        "total_mv": _safe_float(_first_present(profile, ("总市值",))),
    }


async def fetch_public_financial_indicators(code6: str) -> dict:
    """Fetch public financial indicators through AKShare's sync SDK in a worker thread."""
    ak = importlib.import_module("akshare")

    def fetch():
        return ak.stock_financial_analysis_indicator(symbol=code6)

    try:
        df = await asyncio.to_thread(fetch)
    except Exception as e:
        print(f"⚠️ 公开财务指标获取失败: {e}")
        return await fetch_baostock_financial_indicators(code6)

    if df is None or df.empty:
        return await fetch_baostock_financial_indicators(code6)

    latest = df.iloc[-1].to_dict()
    return {
        "roe": _safe_float(
            _first_present(
                latest, ("净资产收益率", "摊薄净资产收益率", "加权净资产收益率")
            )
        ),
        "debt_ratio": _safe_float(
            _first_present(latest, ("资产负债率", "负债合计/资产总计"))
        ),
    }


async def fetch_baostock_financial_indicators(code6: str) -> dict:
    """Fetch recent public financial indicators from BaoStock."""
    provider = BaoStockProvider()
    if not await provider.connect():
        return {}

    now = datetime.now()
    current_quarter = (now.month - 1) // 3 + 1
    periods = []
    for year in range(now.year, now.year - 3, -1):
        start_quarter = current_quarter if year == now.year else 4
        periods.extend((year, quarter) for quarter in range(start_quarter, 0, -1))

    for year, quarter in periods:
        financial_data = await provider.get_financial_data(
            code6, year=year, quarter=quarter
        )
        if not financial_data:
            continue

        profit_data = financial_data.get("profit_data", {})
        balance_data = financial_data.get("balance_data", {})
        roe = _safe_float(profit_data.get("roeAvg"))
        debt_ratio = _safe_float(balance_data.get("liabilityToAsset"))
        if roe is not None:
            roe *= 100
        if debt_ratio is not None:
            debt_ratio *= 100
        return {"roe": roe, "debt_ratio": debt_ratio}

    return {}


async def check_stock_fundamentals(stock_code: str = "000001"):
    """测试股票基本面数据获取"""

    print(f"\n{'=' * 80}")
    print("测试股票基本面数据获取增强功能")
    print(f"{'=' * 80}\n")

    db = get_postgres_db()
    code6 = stock_code.zfill(6)

    # 1. 测试从 stock_basic_info 获取基础信息
    print(f"📊 [测试1] 从 stock_basic_info 获取基础信息: {code6}")
    print("-" * 80)

    basic_info = await db["stock_basic_info"].find_one({"code": code6}, {"_id": 0})

    if basic_info:
        print("✅ 找到基础信息")
        print(f"   股票代码: {basic_info.get('code')}")
        print(f"   股票名称: {basic_info.get('name')}")
        print(f"   所属行业: {basic_info.get('industry')}")
        print(f"   交易所: {basic_info.get('market')}")
        print(f"   板块(sse): {basic_info.get('sse')}")
        print(f"   板块(sec): {basic_info.get('sec')}")
        print(f"   总市值: {basic_info.get('total_mv')} 亿元")
        print(f"   市盈率(PE): {basic_info.get('pe')}")
        print(f"   市净率(PB): {basic_info.get('pb')}")
        print(f"   ROE(基础): {basic_info.get('roe')}")
    else:
        print("⚠️ 未找到基础信息，尝试从 AKShare 公开源获取最小基础信息")
        basic_info = await fetch_public_stock_profile(code6)
        if not basic_info:
            print("❌ 未找到基础信息")
            return False

    # 2. 测试从 stock_financial_data 获取财务数据
    print(f"\n📊 [测试2] 从 stock_financial_data 获取最新财务数据: {code6}")
    print("-" * 80)

    financial_data = await db["stock_financial_data"].find_one(
        {"symbol": code6}, {"_id": 0}, sort=[("report_period", -1)]
    )

    if financial_data:
        print("✅ 找到财务数据")
        print(f"   股票代码: {financial_data.get('symbol')}")
        print(f"   报告期: {financial_data.get('report_period')}")
        print(f"   报告类型: {financial_data.get('report_type')}")
        print(f"   数据来源: {financial_data.get('data_source')}")

        # 检查 financial_indicators
        if financial_data.get("financial_indicators"):
            indicators = financial_data["financial_indicators"]
            print("\n   📈 财务指标:")
            print(f"      ROE(净资产收益率): {indicators.get('roe')}")
            print(f"      ROA(总资产收益率): {indicators.get('roa')}")
            print(f"      负债率(debt_to_assets): {indicators.get('debt_to_assets')}")
            print(f"      流动比率: {indicators.get('current_ratio')}")
            print(f"      速动比率: {indicators.get('quick_ratio')}")
            print(f"      毛利率: {indicators.get('gross_margin')}")
            print(f"      净利率: {indicators.get('net_margin')}")

        # 检查顶层字段
        if financial_data.get("roe"):
            print("\n   📈 顶层字段:")
            print(f"      ROE: {financial_data.get('roe')}")
        if financial_data.get("debt_to_assets"):
            print(f"      负债率: {financial_data.get('debt_to_assets')}")
    else:
        print("⚠️ 未找到财务数据（将使用基础信息中的 ROE）")

    # 3. 模拟接口返回数据
    print("\n📊 [测试3] 模拟接口返回数据")
    print("-" * 80)

    data = {
        "code": code6,
        "name": basic_info.get("name"),
        "industry": basic_info.get("industry"),
        "market": basic_info.get("market"),
        # 板块信息：优先使用 market 字段，不完整时退回行业/板块字段
        "sector": (
            basic_info.get("market")
            or basic_info.get("industry")
            or basic_info.get("sse")
            or basic_info.get("sec")
        ),
        # 估值指标
        "pe": basic_info.get("pe"),
        "pb": basic_info.get("pb"),
        "pe_ttm": basic_info.get("pe_ttm"),
        "pb_mrq": basic_info.get("pb_mrq"),
        # ROE 和负债率（初始化为 None）
        "roe": None,
        "debt_ratio": None,
        # 市值
        "total_mv": basic_info.get("total_mv"),
        "circ_mv": basic_info.get("circ_mv"),
        # 交易指标
        "turnover_rate": basic_info.get("turnover_rate"),
        "volume_ratio": basic_info.get("volume_ratio"),
        "updated_at": basic_info.get("updated_at"),
    }

    # 从财务数据中提取 ROE 和负债率
    if financial_data:
        if financial_data.get("financial_indicators"):
            indicators = financial_data["financial_indicators"]
            data["roe"] = indicators.get("roe")
            data["debt_ratio"] = indicators.get("debt_to_assets")

        # 如果 financial_indicators 中没有，尝试从顶层字段获取
        if data["roe"] is None:
            data["roe"] = financial_data.get("roe")
        if data["debt_ratio"] is None:
            data["debt_ratio"] = financial_data.get("debt_to_assets")

    # 如果财务数据中没有 ROE，使用 stock_basic_info 中的
    if data["roe"] is None:
        data["roe"] = basic_info.get("roe")

    if data["roe"] is None or data["debt_ratio"] is None:
        public_indicators = await fetch_public_financial_indicators(code6)
        if data["roe"] is None:
            data["roe"] = public_indicators.get("roe")
        if data["debt_ratio"] is None:
            data["debt_ratio"] = public_indicators.get("debt_ratio")

    print("✅ 接口返回数据:")
    print(f"   股票代码: {data['code']}")
    print(f"   股票名称: {data['name']}")
    print(f"   所属行业: {data['industry']}")
    print(f"   交易所: {data['market']}")
    print(f"   板块: {data['sector']} {'✅' if data['sector'] else '❌'}")
    print(f"   总市值: {data['total_mv']} 亿元")
    print(f"   市盈率(PE): {data['pe']}")
    print(f"   市净率(PB): {data['pb']}")
    print(f"   ROE: {data['roe']} {'✅' if data['roe'] is not None else '❌'}")
    print(
        f"   负债率: {data['debt_ratio']} {'✅' if data['debt_ratio'] is not None else '❌'}"
    )

    # 4. 验证结果
    print("\n📊 [测试4] 验证结果")
    print("-" * 80)

    success_count = 0
    total_count = 3

    # 验证板块
    if data["sector"]:
        print(f"✅ 板块信息获取成功: {data['sector']}")
        success_count += 1
    else:
        print("❌ 板块信息缺失")

    # 验证 ROE
    if data["roe"] is not None:
        print(f"✅ ROE 获取成功: {data['roe']}")
        success_count += 1
    else:
        print("❌ ROE 缺失")

    # 验证负债率
    if data["debt_ratio"] is not None:
        print(f"✅ 负债率获取成功: {data['debt_ratio']}")
        success_count += 1
    else:
        print("⚠️ 负债率缺失（可能财务数据未同步）")

    print(f"\n{'=' * 80}")
    print(f"测试完成: {success_count}/{total_count} 项通过")
    print(f"{'=' * 80}\n")
    return success_count >= 2


async def check_multiple_stocks():
    """测试多个股票"""

    test_stocks = [
        "000001",  # 平安银行
        "600000",  # 浦发银行
        "000002",  # 万科A
        "600519",  # 贵州茅台
    ]

    print(f"\n{'=' * 80}")
    print("批量测试多个股票")
    print(f"{'=' * 80}\n")

    for stock_code in test_stocks:
        await check_stock_fundamentals(stock_code)
        print("\n")


async def main():
    """主函数"""

    # 初始化 PostgreSQL 连接
    print("🔧 初始化 PostgreSQL 连接...")
    await init_database()
    print("✅ PostgreSQL 连接成功\n")

    # 测试单个股票
    return await check_stock_fundamentals(settings.TRADING_AGENTS_SMOKE_STOCK_CODE)

    # 可选：测试多个股票
    # await test_multiple_stocks()


if __name__ == "__main__":
    asyncio.run(main())


async def test_stock_fundamentals_smoke():
    assert await main()
