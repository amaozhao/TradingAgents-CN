"""测试 Postgres document store 查询"""

from app.db.documentstore import create_sync_client


def main() -> None:
    client = create_sync_client()
    db = client["trading_agents"]

    print("=" * 60)
    print("🔍 测试查询 market_quotes")
    print("=" * 60)

    # 测试不同的查询条件
    queries = [
        {"code": "300750"},
        {"symbol": "300750"},
        {"code": "300750", "symbol": "300750"},
    ]

    try:
        for query in queries:
            print(f"\n查询条件: {query}")
            result = db.market_quotes.find_one(query, {"_id": 0})
            if result:
                print("  ✅ 找到数据")
                print(f"  - volume: {result.get('volume')}")
                print(f"  - amount: {result.get('amount')}")
                print(f"  - volume_ratio: {result.get('volume_ratio')}")
            else:
                print("  ❌ 未找到数据")
    finally:
        client.close()


if __name__ == "__main__":
    main()
