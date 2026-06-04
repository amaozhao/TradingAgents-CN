#!/usr/bin/env python3
"""
测试 config_service 读取的配置
"""

import asyncio
import importlib


async def main():
    """主函数"""
    print("=" * 60)
    print("📊 测试 config_service 读取的配置")
    print("=" * 60)

    try:
        config_service = getattr(
            importlib.import_module("app.services.config"), "config_service"
        )

        # 获取系统配置
        config = await config_service.get_system_config()

        if config:
            print(f"\n✅ 获取到配置，版本: {config.version}")
            print(f"   LLM 配置数量: {len(config.llm_configs)}")
            print(f"   系统设置数量: {len(config.system_settings)}")

            # 打印模型相关的设置
            print("\n模型相关设置:")
            for key in ["default_model", "quick_analysis_model", "deep_analysis_model"]:
                value = config.system_settings.get(key)
                print(f"  {key}: {value}")

            # 打印所有设置
            print("\n所有系统设置:")
            json = importlib.import_module("json")
            print(json.dumps(config.system_settings, indent=2, ensure_ascii=False))
        else:
            print("\n❌ 未获取到配置")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
