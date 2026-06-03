#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试AKShare财务数据获取功能
"""

import akshare as ak
import pandas as pd

def test_akshare_financial_apis():
    """测试AKShare财务数据API"""
    print("=" * 60)
    print("🧪 直接测试AKShare财务数据API")
    print("=" * 60)

    symbol = '000001'
    print(f"🔍 测试股票: {symbol}")

    # 测试资产负债表
    try:
        print("\n📊 测试资产负债表...")
        balance_sheet = ak.stock_balance_sheet_by_report_em(symbol=symbol)
        if not balance_sheet.empty:
            print(f"✅ 资产负债表获取成功，共{len(balance_sheet)}条记录")
            print(f"📅 最新报告期: {balance_sheet.iloc[0]['报告期']}")
        else:
            print("❌ 资产负债表为空")
    except Exception as e:
        print(f"❌ 资产负债表获取失败: {e}")

    # 测试利润表
    try:
        print("\n📊 测试利润表...")
        income_statement = ak.stock_profit_sheet_by_report_em(symbol=symbol)
        if not income_statement.empty:
            print(f"✅ 利润表获取成功，共{len(income_statement)}条记录")
            print(f"📅 最新报告期: {income_statement.iloc[0]['报告期']}")
        else:
            print("❌ 利润表为空")
    except Exception as e:
        print(f"❌ 利润表获取失败: {e}")

    # 测试现金流量表
    try:
        print("\n📊 测试现金流量表...")
        cash_flow = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
        if not cash_flow.empty:
            print(f"✅ 现金流量表获取成功，共{len(cash_flow)}条记录")
            print(f"📅 最新报告期: {cash_flow.iloc[0]['报告期']}")
        else:
            print("❌ 现金流量表为空")
    except Exception as e:
        print(f"❌ 现金流量表获取失败: {e}")

    # 测试主要财务指标
    try:
        print("\n📊 测试主要财务指标...")
        main_indicators = ak.stock_financial_abstract_ths(symbol=symbol)
        if not main_indicators.empty:
            print(f"✅ 主要财务指标获取成功，共{len(main_indicators)}条记录")
            print("📈 主要指标:")
            for col in main_indicators.columns[:5]:  # 显示前5列
                print(f"   {col}: {main_indicators.iloc[0][col]}")
        else:
            print("❌ 主要财务指标为空")
    except Exception as e:
        print(f"❌ 主要财务指标获取失败: {e}")

def test_akshare_stock_info():
    """测试AKShare股票基本信息"""
    print("\n" + "=" * 60)
    print("📋 测试AKShare股票基本信息")
    print("=" * 60)

    symbol = '000001'
    print(f"🔍 测试股票: {symbol}")

    try:
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        if not stock_info.empty:
            print(f"✅ 股票信息获取成功")
            print("📋 基本信息:")
            for _, row in stock_info.head(10).iterrows():  # 显示前10项
                print(f"   {row['item']}: {row['value']}")
        else:
            print("❌ 股票信息为空")
    except Exception as e:
        print(f"❌ 股票信息获取失败: {e}")

def main():
    """主测试函数"""
    print("🚀 开始直接测试AKShare财务数据API")
    print()

    test_akshare_financial_apis()
    test_akshare_stock_info()

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
