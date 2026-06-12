#!/usr/bin/env python3
"""
测试配置统一
"""

import importlib

import pytest

pytestmark = pytest.mark.integration


# 加载环境变量


def test_config_unification():
    """测试配置统一是否正常工作"""
    print("🔬 测试配置统一")
    print("=" * 60)

    try:
        config_manager = getattr(
            importlib.import_module("trader.config.manager"), "config_manager"
        )

        print("🔧 测试全局配置管理器...")

        # 检查配置目录
        print(f"📁 配置目录: {config_manager.config_dir}")
        print(f"📁 配置目录绝对路径: {config_manager.config_dir.absolute()}")
        print(f"📄 定价文件: {config_manager.pricing_file}")
        print(f"📄 定价文件存在: {config_manager.pricing_file.exists()}")

        # 加载定价配置
        pricing_configs = config_manager.load_pricing()
        print(f"📊 加载的定价配置数量: {len(pricing_configs)}")

        assert pricing_configs, "定价配置为空"
        pricing = pricing_configs[0]
        print(
            f"✅ 找到定价配置: {pricing.provider}/{pricing.model_name}, "
            f"输入¥{pricing.input_price_per_1k}/1K, 输出¥{pricing.output_price_per_1k}/1K"
        )

        # 测试成本计算
        print("\n💰 测试成本计算:")
        deepseek_cost = config_manager.calculate_cost(
            provider=pricing.provider,
            model_name=pricing.model_name,
            input_tokens=1000,
            output_tokens=500,
        )
        print(f"   {pricing.provider}/{pricing.model_name} 成本: ¥{deepseek_cost:.6f}")

        assert deepseek_cost >= 0, "成本计算结果不能为负数"
        print("✅ 成本计算正常")

    except Exception as e:
        print(f"❌ 配置统一测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        pytest.fail(str(e))


def test_config_consistency():
    """测试配置一致性"""
    print("\n🔄 测试配置一致性")
    print("=" * 60)

    try:
        config_manager = getattr(
            importlib.import_module("trader.config.manager"), "config_manager"
        )

        # 配置统一入口应保持稳定，旧 Streamlit Web 配置入口已下线。
        main_config_dir = config_manager.config_dir.absolute()

        print(f"📁 主配置目录: {main_config_dir}")

        assert config_manager.pricing_file.parent.absolute() == main_config_dir
        assert config_manager.models_file.parent.absolute() == main_config_dir
        assert config_manager.settings_file.parent.absolute() == main_config_dir
        print("✅ 配置文件目录一致")

        main_configs = config_manager.load_pricing()

        print(f"📊 主配置数量: {len(main_configs)}")

        assert main_configs, "配置数量为空"
        print("✅ 配置可读取")

    except Exception as e:
        print(f"❌ 配置一致性测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        pytest.fail(str(e))
