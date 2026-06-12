"""
完整测试：验证所有 base_url 修复
"""

import importlib
import sys


def test_create_llm_by_provider():
    """测试 create_llm_by_provider 函数"""
    print("\n" + "=" * 80)
    print("🧪 测试 1: create_llm_by_provider 函数")
    print("=" * 80)

    create_llm_by_provider = getattr(
        importlib.import_module("trader.graph.trading"), "create_llm_by_provider"
    )

    custom_url = "https://dashscope.aliyuncs.com/api/v2"

    print(f"\n创建 LLM，使用自定义 URL: {custom_url}")

    llm = create_llm_by_provider(
        provider="dashscope",
        model="qwen-turbo",
        backend_url=custom_url,
        temperature=0.1,
        max_tokens=2000,
        timeout=60,
    )

    print("✅ LLM 创建成功")
    print(f"   模型: {llm.model_name}")
    print(f"   base_url: {llm.openai_api_base}")

    if llm.openai_api_base != custom_url:
        print("❌ base_url 不正确")
        print(f"   期望: {custom_url}")
        print(f"   实际: {llm.openai_api_base}")
    else:
        print("🎯 ✅ base_url 正确")

    assert llm.openai_api_base == custom_url


def test_trading_graph_init():
    """测试 TradingAgentsGraph 初始化"""
    print("\n" + "=" * 80)
    print("🧪 测试 2: TradingAgentsGraph 初始化")
    print("=" * 80)

    TradingAgentsGraph = getattr(
        importlib.import_module("trader.graph.trading"), "TradingAgentsGraph"
    )
    DEFAULT_CONFIG = getattr(
        importlib.import_module("trader.default"), "DEFAULT_CONFIG"
    )

    custom_url = "https://dashscope.aliyuncs.com/api/v2"

    print(f"\n创建 TradingGraph，使用自定义 URL: {custom_url}")

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "dashscope"
    config["deep_think_llm"] = "qwen-turbo"
    config["quick_think_llm"] = "qwen-turbo"
    config["backend_url"] = custom_url  # 添加自定义 URL
    config["online_tools"] = False  # 关闭在线工具以加快测试
    config["memory_enabled"] = False  # 关闭记忆以加快测试

    graph = TradingAgentsGraph(
        selected_analysts=["fundamentals", "market"],
        config=config,
    )

    print("✅ TradingGraph 创建成功")
    print(f"   Deep thinking LLM: {graph.deep_thinking_llm.model_name}")
    print(f"   Deep thinking base_url: {graph.deep_thinking_llm.openai_api_base}")
    print(f"   Quick thinking LLM: {graph.quick_thinking_llm.model_name}")
    print(f"   Quick thinking base_url: {graph.quick_thinking_llm.openai_api_base}")

    success = True

    if graph.deep_thinking_llm.openai_api_base == custom_url:
        print("🎯 ✅ Deep thinking LLM base_url 正确")
    else:
        print("❌ Deep thinking LLM base_url 不正确")
        print(f"   期望: {custom_url}")
        print(f"   实际: {graph.deep_thinking_llm.openai_api_base}")
        success = False

    if graph.quick_thinking_llm.openai_api_base == custom_url:
        print("🎯 ✅ Quick thinking LLM base_url 正确")
    else:
        print("❌ Quick thinking LLM base_url 不正确")
        print(f"   期望: {custom_url}")
        print(f"   实际: {graph.quick_thinking_llm.openai_api_base}")
        success = False

    assert success


def test_fundamentals_analyst():
    """测试基本面分析师"""
    print("\n" + "=" * 80)
    print("🧪 测试 3: 基本面分析师")
    print("=" * 80)

    ChatDashScopeOpenAI = getattr(
        importlib.import_module("trader.llm.adapters"), "ChatDashScopeOpenAI"
    )
    create_fundamentals_analyst = getattr(
        importlib.import_module("trader.agents.analysts.fundamentals"),
        "create_fundamentals_analyst",
    )
    Toolkit = getattr(importlib.import_module("trader.agents.utils.utils"), "Toolkit")
    DEFAULT_CONFIG = getattr(
        importlib.import_module("trader.default"), "DEFAULT_CONFIG"
    )

    custom_url = "https://dashscope.aliyuncs.com/api/v2"

    print(f"\n创建 LLM，使用自定义 URL: {custom_url}")

    llm = ChatDashScopeOpenAI(
        model="qwen-turbo",
        api_key="sk-test-dashscope-base-url-only",
        base_url=custom_url,
        temperature=0.1,
        max_tokens=2000,
    )

    print("✅ LLM 创建成功")
    print(f"   模型: {llm.model_name}")
    print(f"   base_url: {llm.openai_api_base}")

    # 创建工具包
    config = DEFAULT_CONFIG.copy()
    config["online_tools"] = False
    toolkit = Toolkit(config)

    # 创建基本面分析师
    print("\n创建基本面分析师...")
    create_fundamentals_analyst(llm, toolkit)

    print("✅ 基本面分析师创建成功")

    # 模拟分析师内部创建新 LLM 实例的逻辑
    print("\n模拟分析师内部创建新 LLM 实例...")

    if hasattr(llm, "__class__") and "DashScope" in llm.__class__.__name__:
        print("✅ 检测到阿里百炼模型")

        # 获取原始 LLM 的 base_url
        original_base_url = getattr(llm, "openai_api_base", None)
        print(f"✅ 获取原始 base_url: {original_base_url}")

        # 创建新实例
        fresh_llm = ChatDashScopeOpenAI(
            model=llm.model_name,
            api_key="sk-test-dashscope-base-url-only",
            base_url=original_base_url if original_base_url else None,
            temperature=llm.temperature,
            max_tokens=getattr(llm, "max_tokens", 2000),
        )

        print("✅ 创建新 LLM 实例")
        print(f"   模型: {fresh_llm.model_name}")
        print(f"   base_url: {fresh_llm.openai_api_base}")

        if fresh_llm.openai_api_base != custom_url:
            print("\n❌ 错误！新实例的 base_url 不正确")
            print(f"   期望: {custom_url}")
            print(f"   实际: {fresh_llm.openai_api_base}")
        else:
            print("\n🎯 ✅ 完美！新实例的 base_url 正确")

        assert fresh_llm.openai_api_base == custom_url
    else:
        print("⚠️ 未检测到阿里百炼模型")
        raise AssertionError("未检测到阿里百炼模型")


def main():
    print("=" * 80)
    print("🧪 完整测试：验证所有 base_url 修复")
    print("=" * 80)

    results = []

    # 测试 1
    try:
        test_create_llm_by_provider()
        results.append(("create_llm_by_provider", True))
    except Exception as e:
        print(f"\n❌ 测试 1 失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        results.append(("create_llm_by_provider", False))

    # 测试 2
    try:
        test_trading_graph_init()
        results.append(("TradingAgentsGraph 初始化", True))
    except Exception as e:
        print(f"\n❌ 测试 2 失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        results.append(("TradingAgentsGraph 初始化", False))

    # 测试 3
    try:
        test_fundamentals_analyst()
        results.append(("基本面分析师", True))
    except Exception as e:
        print(f"\n❌ 测试 3 失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        results.append(("基本面分析师", False))

    # 总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，请检查上面的详细信息")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
