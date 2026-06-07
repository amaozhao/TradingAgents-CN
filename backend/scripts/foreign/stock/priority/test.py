#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试港股和美股数据源优先级配置
验证是否正确从数据库读取优先级
"""

import asyncio

from app.core.database import get_postgres_db, init_database
from app.services.stocks.foreign import ForeignStockService


async def test_priority():
    """测试数据源优先级读取"""
    print("=" * 80)
    print("📊 测试港股和美股数据源优先级配置")
    print("=" * 80)

    await init_database()

    # 获取数据库连接（异步）
    db = get_postgres_db()

    # 初始化服务
    service = ForeignStockService(db=db)

    # 测试港股优先级
    print("\n🇭🇰 港股数据源优先级:")
    print("-" * 80)
    hk_priority = await service._get_source_priority("HK")
    print(f"优先级列表: {hk_priority}")
    assert hk_priority

    # 测试美股优先级
    print("\n🇺🇸 美股数据源优先级:")
    print("-" * 80)
    us_priority = await service._get_source_priority("US")
    print(f"优先级列表: {us_priority}")
    assert us_priority

    # 测试A股优先级（参考）
    print("\n🇨🇳 A股数据源优先级（参考）:")
    print("-" * 80)
    cn_priority = await service._get_source_priority("CN")
    print(f"优先级列表: {cn_priority}")
    assert cn_priority

    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_priority())
