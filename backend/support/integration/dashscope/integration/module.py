#!/usr/bin/env python3
"""
阿里百炼大模型集成测试脚本
用于验证 TradingAgents 中的阿里百炼集成是否正常工作
"""

import importlib
import sys

from app.core.config import settings as app_settings

# 加载 .env 文件


def test_import():
    """测试导入是否正常"""
    print("🔍 测试1: 检查模块导入...")
    try:
        getattr(importlib.import_module("trader.llm.adapters"), "ChatDashScope")
        print("✅ ChatDashScope 导入成功")

        getattr(importlib.import_module("trader.graph.trading"), "TradingAgentsGraph")
        print("✅ TradingAgentsGraph 导入成功")

        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_api_key():
    """测试API密钥配置"""
    print("\n🔍 测试2: 检查API密钥配置...")

    dashscope_key = app_settings.text_value("DASHSCOPE_API_KEY")
    finnhub_key = app_settings.text_value("FINNHUB_API_KEY")

    if not dashscope_key:
        print("❌ 未找到 DASHSCOPE_API_KEY 环境变量")
        print("💡 请设置: set DASHSCOPE_API_KEY=your_api_key")
        return False
    else:
        print(f"✅ DASHSCOPE_API_KEY: {dashscope_key[:10]}...")

    if not finnhub_key:
        print("❌ 未找到 FINNHUB_API_KEY 环境变量")
        print("💡 请设置: set FINNHUB_API_KEY=your_api_key")
        return False
    else:
        print(f"✅ FINNHUB_API_KEY: {finnhub_key[:10]}...")

    return True


def test_dashscope_connection():
    """测试阿里百炼连接"""
    print("\n🔍 测试3: 检查阿里百炼连接...")

    try:
        dashscope = importlib.import_module("dashscope")
        Generation = getattr(importlib.import_module("dashscope"), "Generation")

        # 设置API密钥
        dashscope.api_key = app_settings.text_value("DASHSCOPE_API_KEY")

        # 测试简单调用
        response = Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
            result_format="message",
        )

        if response.status_code == 200:
            content = response.output.choices[0].message.content
            print(f"✅ 阿里百炼连接成功: {content}")
            return True
        else:
            print(f"❌ 阿里百炼连接失败: {response.code} - {response.message}")
            return False

    except Exception as e:
        print(f"❌ 阿里百炼连接测试失败: {e}")
        return False


def test_langchain_adapter():
    """测试LangChain适配器"""
    print("\n🔍 测试4: 检查LangChain适配器...")

    try:
        ChatDashScope = getattr(
            importlib.import_module("trader.llm.adapters"), "ChatDashScope"
        )
        HumanMessage = getattr(
            importlib.import_module("langchain_core.messages"), "HumanMessage"
        )

        # 创建适配器实例
        llm = ChatDashScope(model="qwen-turbo")

        # 测试调用
        messages = [HumanMessage(content="请回复'适配器工作正常'")]
        response = llm.invoke(messages)

        print(f"✅ LangChain适配器工作正常: {response.content}")
        return True

    except Exception as e:
        print(f"❌ LangChain适配器测试失败: {e}")
        return False


def test_trading_graph_config():
    """测试TradingGraph配置"""
    print("\n🔍 测试5: 检查TradingGraph配置...")

    try:
        TradingAgentsGraph = getattr(
            importlib.import_module("trader.graph.trading"), "TradingAgentsGraph"
        )
        DEFAULT_CONFIG = getattr(
            importlib.import_module("trader.default"), "DEFAULT_CONFIG"
        )

        # 创建阿里百炼配置
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "dashscope"
        config["deep_think_llm"] = "qwen-plus"
        config["quick_think_llm"] = "qwen-turbo"

        # 尝试初始化（不运行分析）
        TradingAgentsGraph(debug=False, config=config)

        print("✅ TradingGraph 配置成功")
        print(f"   深度思考模型: {config['deep_think_llm']}")
        print(f"   快速思考模型: {config['quick_think_llm']}")
        return True

    except Exception as e:
        print(f"❌ TradingGraph 配置失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 阿里百炼大模型集成测试")
    print("=" * 50)

    tests = [
        test_import,
        test_api_key,
        test_dashscope_connection,
        test_langchain_adapter,
        test_trading_graph_config,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")

    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！阿里百炼集成工作正常")
        print("\n💡 下一步:")
        print("   1. 运行 python demo_dashscope.py 进行完整测试")
        print("   2. 或使用 python -m cli.main analyze 启动交互式分析")
    else:
        print("⚠️  部分测试失败，请检查配置")
        print("\n🔧 故障排除:")
        print("   1. 确认已安装 dashscope: pip install dashscope")
        print("   2. 检查API密钥是否正确设置")
        print("   3. 确认网络连接正常")
        print("   4. 查看详细错误信息")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
