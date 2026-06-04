#!/usr/bin/env python3
"""
测试Web配置管理页面
"""

import importlib
import sys


def test_config_page_import():
    """测试配置页面导入"""
    print("🧪 测试配置管理页面导入")
    print("=" * 50)

    try:
        getattr(importlib.import_module("web.modules.config"), "render_config")
        print("✅ 配置管理页面导入成功")
        return True
    except Exception as e:
        print(f"❌ 配置管理页面导入失败: {e}")
        traceback = importlib.import_module("traceback")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def test_config_manager_import():
    """测试配置管理器导入"""
    print("\n🧪 测试配置管理器导入")
    print("=" * 50)

    try:
        config_manager = getattr(
            importlib.import_module("trader.config.manager"), "config_manager"
        )
        getattr(importlib.import_module("trader.config.manager"), "token_tracker")
        print("✅ 配置管理器导入成功")

        # 测试基本功能
        models = config_manager.load_models()
        print(f"📋 加载了 {len(models)} 个模型配置")

        pricing = config_manager.load_pricing()
        print(f"💰 加载了 {len(pricing)} 个定价配置")

        settings = config_manager.load_settings()
        print(f"⚙️ 加载了 {len(settings)} 个系统设置")

        return True
    except Exception as e:
        print(f"❌ 配置管理器导入失败: {e}")
        traceback = importlib.import_module("traceback")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def test_streamlit_components():
    """测试Streamlit组件"""
    print("\n🧪 测试Streamlit组件")
    print("=" * 50)

    try:
        importlib.import_module("streamlit")
        importlib.import_module("pandas")
        importlib.import_module("plotly.express")
        importlib.import_module("plotly.graph_objects")

        print("✅ Streamlit导入成功")
        print("✅ Pandas导入成功")
        print("✅ Plotly导入成功")

        return True
    except Exception as e:
        print(f"❌ Streamlit组件导入失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 Web配置管理页面测试")
    print("=" * 60)

    tests = [
        ("Streamlit组件", test_streamlit_components),
        ("配置管理器", test_config_manager_import),
        ("配置页面", test_config_page_import),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")

    print(f"\n📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！配置管理页面可以正常使用")
        print("\n💡 使用方法:")
        print("1. 启动Web应用: python -m streamlit run web/app.py")
        print("2. 在侧边栏选择 '⚙️ 配置管理'")
        print("3. 配置API密钥、模型参数和费率设置")
        print("4. 查看使用统计和成本分析")
        return True
    else:
        print("❌ 部分测试失败，请检查配置")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
