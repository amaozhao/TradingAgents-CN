#!/usr/bin/env python3
"""
测试AKShare性能优化
"""
import importlib
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import time
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

def test_akshare_performance():
    """测试AKShare性能"""
    print("=" * 60)
    print("🚀 测试AKShare性能优化")
    print("=" * 60)

    try:
        AKShareAdapter = getattr(importlib.import_module('app.services.sources'), 'AKShareAdapter')

        adapter = AKShareAdapter()

        if not adapter.is_available():
            print("❌ AKShare适配器不可用")
            return

        print("✅ AKShare适配器可用")

        # 测试daily_basic获取性能
        trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        print(f"📅 测试获取{trade_date}的数据...")

        start_time = time.time()
        df = adapter.get_daily_basic(trade_date)
        end_time = time.time()

        duration = end_time - start_time

        if df is not None and not df.empty:
            print(f"✅ daily_basic数据获取成功:")
            print(f"   📊 记录数量: {len(df)}条")
            print(f"   ⏱️ 耗时: {duration:.1f}秒")
            print(f"   🚀 平均速度: {len(df)/duration:.1f}条/秒")

            # 检查数据质量
            close_count = df['close'].notna().sum() if 'close' in df.columns else 0
            mv_count = df['total_mv'].notna().sum() if 'total_mv' in df.columns else 0

            print(f"   📈 数据质量:")
            print(f"     有收盘价数据: {close_count}只 ({close_count/len(df)*100:.1f}%)")
            print(f"     有总市值数据: {mv_count}只 ({mv_count/len(df)*100:.1f}%)")

            # 显示样本数据
            print(f"   📋 样本数据:")
            for i, row in df.head(3).iterrows():
                ts_code = row.get('ts_code', 'N/A')
                name = row.get('name', 'N/A')
                close = row.get('close', 'N/A')
                total_mv = row.get('total_mv', 'N/A')
                print(f"     {ts_code} - {name}: 价格={close}, 市值={total_mv}")

            # 性能评估
            if duration < 30:
                print(f"   🎯 性能评估: 优秀 (< 30秒)")
            elif duration < 60:
                print(f"   ⚠️ 性能评估: 可接受 (< 60秒)")
            else:
                print(f"   ❌ 性能评估: 需要优化 (> 60秒)")

        else:
            print(f"❌ daily_basic数据获取失败，耗时: {duration:.1f}秒")

    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        traceback = importlib.import_module('traceback')
        traceback.print_exc()

def test_web_api_simulation():
    """模拟Web API调用"""
    print("\n" + "=" * 60)
    print("🌐 模拟Web API调用测试")
    print("=" * 60)

    try:
        DataSourceManager = getattr(importlib.import_module('app.services.sources'), 'DataSourceManager')

        manager = DataSourceManager()

        # 模拟Web API的测试逻辑
        print("📊 模拟测试AKShare数据源...")

        start_time = time.time()

        # 1. 测试股票列表
        print("   1. 测试股票列表获取...")
        stock_start = time.time()

        # 找到AKShare适配器
        akshare_adapter = None
        for adapter in manager.get_available_adapters():
            if adapter.name == 'akshare':
                akshare_adapter = adapter
                break

        if not akshare_adapter:
            print("   ❌ 未找到AKShare适配器")
            return

        stock_df = akshare_adapter.get_stock_list()
        stock_time = time.time() - stock_start

        if stock_df is not None and not stock_df.empty:
            print(f"   ✅ 股票列表: {len(stock_df)}条记录，耗时: {stock_time:.1f}秒")
        else:
            print(f"   ❌ 股票列表获取失败")
            return

        # 2. 测试交易日期
        print("   2. 测试交易日期获取...")
        date_start = time.time()
        latest_date = akshare_adapter.get_latest_trade_date()
        date_time = time.time() - date_start
        print(f"   ✅ 最新交易日期: {latest_date}，耗时: {date_time:.1f}秒")

        # 3. 测试财务数据
        print("   3. 测试财务数据获取...")
        basic_start = time.time()
        basic_df = akshare_adapter.get_daily_basic(latest_date)
        basic_time = time.time() - basic_start

        if basic_df is not None and not basic_df.empty:
            print(f"   ✅ 财务数据: {len(basic_df)}条记录，耗时: {basic_time:.1f}秒")
        else:
            print(f"   ❌ 财务数据获取失败，耗时: {basic_time:.1f}秒")

        total_time = time.time() - start_time
        print(f"\n📊 总体测试结果:")
        print(f"   总耗时: {total_time:.1f}秒")
        print(f"   股票列表: {stock_time:.1f}秒")
        print(f"   交易日期: {date_time:.1f}秒")
        print(f"   财务数据: {basic_time:.1f}秒")

        # Web超时评估
        if total_time < 30:
            print(f"   🎯 Web兼容性: 优秀 (< 30秒)")
        elif total_time < 60:
            print(f"   ⚠️ Web兼容性: 可接受 (< 60秒)")
        else:
            print(f"   ❌ Web兼容性: 超时风险 (> 60秒)")

    except Exception as e:
        print(f"❌ Web API模拟测试失败: {e}")
        traceback = importlib.import_module('traceback')
        traceback.print_exc()

if __name__ == "__main__":
    test_akshare_performance()
    test_web_api_simulation()
