#!/usr/bin/env python3
"""
测试000001历史数据同步
"""

import asyncio

from app.core.database import close_database, init_database
from app.services.market.historical import get_historical_data_service
from trader.config.databases import get_postgres_client
from trader.flows.providers.china.akshare import AKShareProvider


async def test_000001():
    print("🔍 测试000001 AkShare历史数据同步")
    print("=" * 60)

    await init_database()
    try:
        provider = AKShareProvider()
        await provider.connect()
        service = await get_historical_data_service()

        # 检查数据库状态（保存前）
        client = get_postgres_client()
        db = client.get_database("trading_agents")
        collection = db.stock_daily_quotes

        before_count = collection.count_documents(
            {"symbol": "000001", "data_source": "akshare"}
        )
        print(f"📊 000001 AkShare记录数（保存前）: {before_count}")

        # 获取并保存2024年1月的数据
        df = await provider.get_historical_data("000001", "2024-01-01", "2024-01-31")
        assert df is not None and not df.empty
        print(f"📥 获取到 {len(df)} 条记录")

        saved_count = await service.save_historical_data(
            symbol="000001",
            data=df,
            data_source="akshare",
            market="CN",
            period="daily",
        )
        print(f"💾 保存了 {saved_count} 条记录")
        assert saved_count > 0

        # 检查数据库状态（保存后）
        after_count = collection.count_documents(
            {"symbol": "000001", "data_source": "akshare"}
        )
        print(f"📊 000001 AkShare记录数（保存后）: {after_count}")
        print(f"📈 新增记录数: {after_count - before_count}")
        assert after_count >= before_count

        # 查询2024年1月的数据
        jan_2024_count = collection.count_documents(
            {
                "symbol": "000001",
                "data_source": "akshare",
                "trade_date": {"$gte": "2024-01-01", "$lte": "2024-01-31"},
            }
        )
        print(f"📅 2024年1月数据: {jan_2024_count} 条")
        assert jan_2024_count > 0

        # 显示前5条记录
        print("\n📋 2024年1月前5条记录:")
        records = list(
            collection.find(
                {
                    "symbol": "000001",
                    "data_source": "akshare",
                    "trade_date": {"$gte": "2024-01-01", "$lte": "2024-01-31"},
                }
            )
            .sort("trade_date", 1)
            .limit(5)
        )

        for record in records:
            trade_date = record.get("trade_date", "N/A")
            close = record.get("close", "N/A")
            volume = record.get("volume", "N/A")
            print(f"  {trade_date}: 收盘={close}, 成交量={volume}")

        client.close()
        print("=" * 60)
        print("✅ 测试完成！")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(test_000001())
