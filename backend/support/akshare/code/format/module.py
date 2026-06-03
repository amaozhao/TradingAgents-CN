"""
测试 AKShare 两个实时行情接口返回的股票代码格式
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_akshare_interfaces():
    """测试 AKShare 的两个实时行情接口"""
    print("\n" + "="*60)
    print("🧪 测试 AKShare 实时行情接口的股票代码格式")
    print("="*60)

    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        print("❌ AKShare 未安装，跳过测试")
        return

    # 测试 1: 新浪财经接口
    print("\n" + "-"*60)
    print("测试 1: stock_zh_a_spot() - 新浪财经接口")
    print("-"*60)

    try:
        print("📡 正在获取数据...")
        df_sina = ak.stock_zh_a_spot()

        if df_sina is None or df_sina.empty:
            print("⚠️ 新浪接口返回空数据")
        else:
            print(f"✅ 获取到 {len(df_sina)} 条数据")
            print(f"\n📋 列名: {list(df_sina.columns)}")

            # 查找代码列
            code_col = None
            for col in ["代码", "code", "symbol", "股票代码"]:
                if col in df_sina.columns:
                    code_col = col
                    break

            if code_col:
                print(f"\n🔍 代码列名: '{code_col}'")
                print(f"\n📊 前10个股票代码样本:")

                for i, code in enumerate(df_sina[code_col].head(10), 1):
                    code_str = str(code)
                    code_len = len(code_str)
                    has_prefix = not code_str.isdigit()

                    status = "⚠️" if has_prefix or code_len != 6 else "✅"
                    print(f"   {status} {i:2d}. {code_str:12s} | 长度: {code_len} | 纯数字: {not has_prefix}")

                # 统计异常代码
                abnormal_codes = []
                for code in df_sina[code_col]:
                    code_str = str(code)
                    if len(code_str) != 6 or not code_str.isdigit():
                        abnormal_codes.append(code_str)

                if abnormal_codes:
                    print(f"\n   ⚠️ 发现 {len(abnormal_codes)} 个异常代码（前5个）:")
                    for code in abnormal_codes[:5]:
                        print(f"      - {code}")
                else:
                    print(f"\n   ✅ 所有代码都是标准的6位数字格式")
            else:
                print("❌ 未找到代码列")

    except Exception as e:
        print(f"❌ 新浪接口测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试 2: 东方财富接口
    print("\n" + "-"*60)
    print("测试 2: stock_zh_a_spot_em() - 东方财富接口")
    print("-"*60)

    try:
        print("📡 正在获取数据...")
        df_em = ak.stock_zh_a_spot_em()

        if df_em is None or df_em.empty:
            print("⚠️ 东方财富接口返回空数据")
        else:
            print(f"✅ 获取到 {len(df_em)} 条数据")
            print(f"\n📋 列名: {list(df_em.columns)}")

            # 查找代码列
            code_col = None
            for col in ["代码", "code", "symbol", "股票代码"]:
                if col in df_em.columns:
                    code_col = col
                    break

            if code_col:
                print(f"\n🔍 代码列名: '{code_col}'")
                print(f"\n📊 前10个股票代码样本:")

                for i, code in enumerate(df_em[code_col].head(10), 1):
                    code_str = str(code)
                    code_len = len(code_str)
                    has_prefix = not code_str.isdigit()

                    status = "⚠️" if has_prefix or code_len != 6 else "✅"
                    print(f"   {status} {i:2d}. {code_str:12s} | 长度: {code_len} | 纯数字: {not has_prefix}")

                # 统计异常代码
                abnormal_codes = []
                for code in df_em[code_col]:
                    code_str = str(code)
                    if len(code_str) != 6 or not code_str.isdigit():
                        abnormal_codes.append(code_str)

                if abnormal_codes:
                    print(f"\n   ⚠️ 发现 {len(abnormal_codes)} 个异常代码（前5个）:")
                    for code in abnormal_codes[:5]:
                        print(f"      - {code}")
                else:
                    print(f"\n   ✅ 所有代码都是标准的6位数字格式")
            else:
                print("❌ 未找到代码列")

    except Exception as e:
        print(f"❌ 东方财富接口测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 对比总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    print("✅ 新浪接口 (stock_zh_a_spot): 代码可能带有交易所前缀（如 sz000001）")
    print("✅ 东方财富接口 (stock_zh_a_spot_em): 需要验证代码格式")
    print("\n💡 建议: 两个接口都应该使用统一的代码标准化逻辑")


if __name__ == "__main__":
    test_akshare_interfaces()
