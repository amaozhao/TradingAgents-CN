#!/usr/bin/env python3
"""
002027 股票代码专项测试
"""

import importlib
from app.core.config import settings as app_settings


def test_002027_specifically():
    """专门测试002027股票代码"""
    print("🔍 002027 专项测试")
    print("=" * 60)

    test_ticker = "002027"

    try:
        get_logger = getattr(
            importlib.import_module("trader.utils.logging.init"), "get_logger"
        )
        logger = get_logger("default")
        logger.setLevel("INFO")

        # 测试1: 数据获取
        print("\n📊 测试1: 数据获取")
        get_china_stock_data_tushare = getattr(
            importlib.import_module("trader.flows.interface"),
            "get_china_stock_data_tushare",
        )
        data = get_china_stock_data_tushare(test_ticker, "2025-07-01", "2025-07-15")

        if "002021" in data:
            print("❌ 数据获取阶段发现错误代码 002021")
            return False
        else:
            print("✅ 数据获取阶段正确")

        # 测试2: 基本面分析
        print("\n💰 测试2: 基本面分析")
        OptimizedChinaDataProvider = getattr(
            importlib.import_module("trader.flows.china"), "OptimizedChinaDataProvider"
        )
        analyzer = OptimizedChinaDataProvider()
        report = analyzer._generate_fundamentals_report(test_ticker, data)

        if "002021" in report:
            print("❌ 基本面分析阶段发现错误代码 002021")
            return False
        else:
            print("✅ 基本面分析阶段正确")

        # 测试3: LLM处理
        print("\n🤖 测试3: LLM处理")
        api_key = app_settings.text_value("DASHSCOPE_API_KEY")
        if api_key:
            ChatDashScopeOpenAI = getattr(
                importlib.import_module("trader.llm.adapters"), "ChatDashScopeOpenAI"
            )
            HumanMessage = getattr(
                importlib.import_module("langchain_core.messages"), "HumanMessage"
            )

            llm = ChatDashScopeOpenAI(
                model="qwen-turbo", temperature=0.1, max_tokens=500
            )

            prompt = f"请分析股票{test_ticker}的基本面，股票名称是分众传媒。要求：1.必须使用正确的股票代码{test_ticker} 2.不要使用任何其他股票代码"

            response = llm.invoke([HumanMessage(content=prompt)])

            if "002021" in response.content:
                print("❌ LLM处理阶段发现错误代码 002021")
                print(f"错误内容: {response.content[:200]}...")
                return False
            else:
                print("✅ LLM处理阶段正确")
        else:
            print("⚠️ 跳过LLM测试（未配置API密钥）")

        print("\n🎉 所有测试通过！002027股票代码处理正确")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    test_002027_specifically()
