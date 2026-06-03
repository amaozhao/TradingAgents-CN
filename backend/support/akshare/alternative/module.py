#!/usr/bin/env python3
"""
测试AKShare的替代财务数据接口
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import pandas as pd

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)

def test_akshare_individual_info():
    """测试AKShare的个股信息接口"""
    print("=" * 60)
    print("🧪 测试AKShare的个股信息接口")
    print("=" * 60)

    try:
        import akshare as ak

        # 测试几个股票
        test_symbols = ['000001', '600000', '000002']

        for symbol in test_symbols:
            print(f"\n📊 测试股票: {symbol}")
            try:
                data = ak.stock_individual_info_em(symbol=symbol)

                if data is not None and not data.empty:
                    print(f"✅ 成功获取{symbol}的信息: {len(data)}条记录")
                    print(f"   数据结构:")
                    for i, row in data.iterrows():
                        item = row.get('item', 'N/A')
                        value = row.get('value', 'N/A')
                        print(f"     {item}: {value}")
                else:
                    print(f"❌ 无法获取{symbol}的信息")

            except Exception as e:
                print(f"❌ 获取{symbol}失败: {e}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

def test_akshare_financial_apis():
    """测试AKShare的其他财务相关API"""
    print("\n" + "=" * 60)
    print("🧪 测试AKShare的其他财务相关API")
    print("=" * 60)

    try:
        import akshare as ak

        # 测试不同的财务API
        apis_to_test = [
            ('stock_zh_a_hist', '股票历史数据'),
            ('stock_financial_abstract', '财务摘要'),
            ('stock_financial_analysis_indicator', '财务分析指标'),
        ]

        test_symbol = '000001'

        for api_name, description in apis_to_test:
            print(f"\n📊 测试 {api_name} ({description}):")
            try:
                if api_name == 'stock_zh_a_hist':
                    # 获取历史数据
                    data = ak.stock_zh_a_hist(symbol=test_symbol, period="daily", start_date="20241201", end_date="20241205", adjust="")
                elif api_name == 'stock_financial_abstract':
                    # 财务摘要
                    data = ak.stock_financial_abstract(symbol=test_symbol)
                elif api_name == 'stock_financial_analysis_indicator':
                    # 财务分析指标
                    data = ak.stock_financial_analysis_indicator(symbol=test_symbol)
                else:
                    continue

                if data is not None and not data.empty:
                    print(f"   ✅ 成功: {len(data)}条记录")
                    print(f"   列名: {list(data.columns)}")
                    if len(data) > 0:
                        print(f"   样本数据:")
                        print(data.head(2))
                else:
                    print(f"   ❌ 无数据")

            except Exception as e:
                print(f"   ❌ 失败: {e}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

def test_akshare_market_data():
    """测试AKShare的市场数据接口"""
    print("\n" + "=" * 60)
    print("🧪 测试AKShare的市场数据接口")
    print("=" * 60)

    try:
        import akshare as ak

        # 测试市场相关的API
        apis_to_test = [
            ('stock_zh_index_spot', '指数实时数据'),
            ('stock_zh_a_hist', '个股历史数据'),
        ]

        for api_name, description in apis_to_test:
            print(f"\n📊 测试 {api_name} ({description}):")
            try:
                if api_name == 'stock_zh_index_spot':
                    # 指数数据
                    data = ak.stock_zh_index_spot()
                elif api_name == 'stock_zh_a_hist':
                    # 个股历史数据
                    data = ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20241201", end_date="20241205", adjust="")
                else:
                    continue

                if data is not None and not data.empty:
                    print(f"   ✅ 成功: {len(data)}条记录")
                    print(f"   列名: {list(data.columns)}")
                    if len(data) > 0:
                        print(f"   前3条数据:")
                        print(data.head(3))
                else:
                    print(f"   ❌ 无数据")

            except Exception as e:
                print(f"   ❌ 失败: {e}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_akshare_individual_info()
    test_akshare_financial_apis()
    test_akshare_market_data()
