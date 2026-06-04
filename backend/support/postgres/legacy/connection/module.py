#!/usr/bin/env python3
"""测试 PostgreSQL document store 兼容连接"""

from app.db.store import create_sync_client


def test_connections():
    """测试 PostgreSQL document store 连接"""

    try:
        client = create_sync_client()
        client.admin.command("ping")
        print("✅ 连接成功")

        collections = client.trader.list_collection_names()
        print(f"📁 trading_agents数据库中的集合: {collections}")

        if "system_configs" in collections:
            count = client.trader.system_configs.count_documents({})
            print(f"📄 system_configs集合中的文档数量: {count}")

        client.close()
        return {"name": "PostgreSQL document store"}

    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return None


if __name__ == "__main__":
    print("🔧 测试 PostgreSQL document store 连接...")
    working_config = test_connections()

    if working_config:
        print(f"\n✅ 找到可用配置: {working_config['name']}")
    else:
        print("\n❌ 没有找到可用的连接配置")
