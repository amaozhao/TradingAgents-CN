"""
简单的港股功能测试
"""

import importlib


def test_basic():
    """基本测试"""
    print("🧪 开始基本港股功能测试...")

    try:
        # 测试股票工具类
        StockUtils = getattr(
            importlib.import_module("trader.utils.stocks"), "StockUtils"
        )

        # 测试港股代码识别
        test_cases = [
            "0700.HK",  # 腾讯
            "9988.HK",  # 阿里巴巴
            "3690.HK",  # 美团
            "000001",  # 平安银行
            "AAPL",  # 苹果
        ]

        for ticker in test_cases:
            market_info = StockUtils.get_market_info(ticker)
            print(
                f"  {ticker}: {market_info['market_name']} ({market_info['currency_name']} {market_info['currency_symbol']})"
            )

        print("✅ 基本测试通过")
        return True

    except Exception as e:
        print(f"❌ 基本测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_basic()
