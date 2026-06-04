"""
测试 AKShare 港股相关接口
验证哪些接口可用，以及它们的功能和返回数据
"""

from datetime import datetime

import akshare as ak
import pandas as pd


def print_separator(title):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_api(api_name, api_func, *args, **kwargs):
    """测试单个API接口"""
    print(f"📊 测试接口: {api_name}")
    print(f"   参数: args={args}, kwargs={kwargs}")
    try:
        result = api_func(*args, **kwargs)

        if isinstance(result, pd.DataFrame):
            print("   ✅ 成功! 返回 DataFrame")
            print(f"   📈 数据行数: {len(result)}")
            print(f"   📋 列名: {list(result.columns)}")
            print("\n   前3行数据:")
            print(result.head(3).to_string())
            return True, result
        else:
            print(f"   ✅ 成功! 返回类型: {type(result)}")
            print(f"   数据: {result}")
            return True, result

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False, None


def main():
    """主测试函数"""

    # 测试股票代码
    test_symbol = "00700"  # 腾讯控股

    print_separator("AKShare 港股接口测试")
    print(f"测试股票: {test_symbol} (腾讯控股)")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ========================================
    # 1. 实时行情接口
    # ========================================
    print_separator("1. 实时行情接口")

    # 1.1 东方财富 - 港股实时行情
    success, df = test_api("stock_hk_spot_em", ak.stock_hk_spot_em)
    if success and df is not None:
        # 查找腾讯控股
        matched = df[df["代码"] == test_symbol]
        if not matched.empty:
            print(f"\n   🎯 找到 {test_symbol}:")
            print(matched.to_string())

    # 1.2 东方财富 - 港股主板实时行情
    success, df = test_api(
        "stock_hk_main_board_spot_em", ak.stock_hk_main_board_spot_em
    )
    if success and df is not None:
        matched = df[df["代码"] == test_symbol]
        if not matched.empty:
            print(f"\n   🎯 找到 {test_symbol}:")
            print(matched.to_string())

    # 1.3 新浪财经 - 港股实时行情
    try:
        success, df = test_api("stock_hk_spot", ak.stock_hk_spot)
        if success and df is not None:
            # 新浪接口的列名是 '代码'，不是 'symbol'
            matched = df[df["代码"] == test_symbol]
            if not matched.empty:
                print(f"\n   🎯 找到 {test_symbol}:")
                print(matched.to_string())
    except AttributeError:
        print("   ⚠️ 接口 stock_hk_spot 不存在")

    # ========================================
    # 2. 历史行情接口
    # ========================================
    print_separator("2. 历史行情接口")

    # 2.1 新浪财经 - 港股历史行情
    success, df = test_api(
        "stock_hk_daily",
        ak.stock_hk_daily,
        symbol=test_symbol,
        adjust="qfq",  # 前复权
    )
    if success and df is not None:
        print("\n   📅 最近5个交易日:")
        print(df.tail(5).to_string())

    # ========================================
    # 3. 个股信息接口
    # ========================================
    print_separator("3. 个股信息接口")

    # 3.1 雪球 - 港股个股信息
    try:
        success, result = test_api(
            "stock_individual_basic_info_hk_xq",
            ak.stock_individual_basic_info_hk_xq,
            symbol=test_symbol,
        )
    except AttributeError:
        print("   ⚠️ 接口 stock_individual_basic_info_hk_xq 不存在")
    except Exception as e:
        print(f"   ❌ 调用失败: {e}")

    # ========================================
    # 4. 股票列表接口
    # ========================================
    print_separator("4. 股票列表接口")

    # 4.1 港股股票列表
    try:
        success, df = test_api("stock_hk_list", ak.stock_hk_list)
    except AttributeError:
        print("   ⚠️ 接口 stock_hk_list 不存在")

    # 4.2 从实时行情获取股票列表
    print("\n📊 从 stock_hk_spot_em 获取股票列表:")
    try:
        df = ak.stock_hk_spot_em()
        if df is not None and not df.empty:
            print(f"   ✅ 共 {len(df)} 只港股")
            print(f"   📋 列名: {list(df.columns)}")
            print("\n   前10只股票:")
            print(df.head(10)[["代码", "名称", "最新价", "涨跌幅"]].to_string())
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    # ========================================
    # 5. 其他可能的接口
    # ========================================
    print_separator("5. 其他港股相关接口")

    # 5.1 港股通成分股
    try:
        success, df = test_api(
            "stock_hk_ggt_components_em", ak.stock_hk_ggt_components_em
        )
    except AttributeError:
        print("   ⚠️ 接口 stock_hk_ggt_components_em 不存在")

    # 5.2 港股通资金流向
    try:
        success, df = test_api("stock_hk_ggt_hist_em", ak.stock_hk_ggt_hist_em)
    except AttributeError:
        print("   ⚠️ 接口 stock_hk_ggt_hist_em 不存在")

    # ========================================
    # 总结
    # ========================================
    print_separator("测试总结")

    print("""
    📊 AKShare 港股接口总结:

    ✅ 可用接口:
    1. stock_hk_spot_em - 东方财富港股实时行情 (推荐)
       - 包含: 代码、名称、最新价、涨跌幅、成交量等
       - 可获取所有港股列表
       - 数据较全面

    2. stock_hk_main_board_spot_em - 东方财富港股主板实时行情
       - 只包含主板股票
       - 数据结构与 stock_hk_spot_em 类似

    3. stock_hk_daily - 新浪财经港股历史行情
       - 需要指定股票代码
       - 支持前复权、后复权
       - 包含: 日期、开盘、收盘、最高、最低、成交量等

    ⚠️ 注意事项:
    - 部分接口可能不存在或已废弃
    - 建议使用 stock_hk_spot_em 作为主要数据源
    - 历史数据使用 stock_hk_daily
    """)


if __name__ == "__main__":
    main()
