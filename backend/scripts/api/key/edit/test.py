#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 API Key 编辑功能

测试场景：
1. 添加新厂家并配置 API Key
2. 更新厂家的 API Key
3. 清空厂家的 API Key（使用环境变量）
4. 验证配置优先级
"""

import asyncio
import sys
import traceback

from app.core.database import init_db
from app.schemas.config import LLMProvider
from app.services.config import ConfigService

# 加载环境变量
TEST_PROVIDER_NAME = "test_provider"


async def cleanup_existing_test_provider(config_service) -> None:
    """删除上一次测试遗留的同名厂家，保证测试幂等。"""
    providers = await config_service.get_llm_providers()
    for provider in providers:
        if provider.name == TEST_PROVIDER_NAME and provider.id:
            await config_service.delete_llm_provider(str(provider.id))


async def add_provider_with_key():
    """测试添加厂家并配置 API Key"""
    # 初始化数据库
    await init_db()

    config_service = ConfigService()
    await cleanup_existing_test_provider(config_service)

    print("=" * 80)
    print("🧪 测试 1: 添加新厂家并配置 API Key")
    print("=" * 80)

    # 创建测试厂家
    test_provider = LLMProvider(
        name=TEST_PROVIDER_NAME,
        display_name="测试厂家",
        description="用于测试 API Key 配置的厂家",
        website="https://test.com",
        api_doc_url="https://test.com/docs",
        default_base_url="https://api.test.com/v1",
        api_key="sk-test-key-1234567890abcdef",  # 有效的 Key
        supported_features=["chat"],
        is_active=True,
    )

    try:
        # 添加厂家
        provider_id = await config_service.add_llm_provider(test_provider)
        print(f"✅ 厂家添加成功，ID: {provider_id}")

        # 获取厂家列表，验证 API Key
        providers = await config_service.get_llm_providers()
        test_prov = next((p for p in providers if p.name == TEST_PROVIDER_NAME), None)

        if test_prov:
            print("✅ 找到测试厂家")
            print(f"   API Key: {_mask_key(test_prov.api_key)}")
            print(f"   来源: {test_prov.extra_config.get('source', 'unknown')}")
            print(f"   已配置: {test_prov.extra_config.get('has_api_key', False)}")
        else:
            print("❌ 未找到测试厂家")

        return provider_id

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback.print_exc()
        return None


async def update_provider_key(provider_id: str):
    """测试更新厂家的 API Key"""
    # 初始化数据库
    await init_db()

    config_service = ConfigService()

    print("\n" + "=" * 80)
    print("🧪 测试 2: 更新厂家的 API Key")
    print("=" * 80)

    try:
        # 更新 API Key
        new_key = "sk-updated-key-9876543210fedcba"
        update_data = {"api_key": new_key}

        success = await config_service.update_llm_provider(provider_id, update_data)

        if success:
            print("✅ API Key 更新成功")

            # 验证更新
            providers = await config_service.get_llm_providers()
            test_prov = next(
                (p for p in providers if p.name == TEST_PROVIDER_NAME), None
            )

            if test_prov:
                print(f"   API Key: {_mask_key(test_prov.api_key)}")
                print(f"   来源: {test_prov.extra_config.get('source', 'unknown')}")
        else:
            print("❌ API Key 更新失败")
        return success

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback.print_exc()
        return False


async def clear_provider_key(provider_id: str):
    """测试清空厂家的 API Key（使用环境变量）"""
    # 初始化数据库
    await init_db()

    config_service = ConfigService()

    print("\n" + "=" * 80)
    print("🧪 测试 3: 清空厂家的 API Key（使用环境变量）")
    print("=" * 80)

    try:
        # 清空 API Key（设置为空字符串）
        update_data = {"api_key": ""}

        success = await config_service.update_llm_provider(provider_id, update_data)

        if success:
            print("✅ API Key 清空成功")

            # 验证更新
            providers = await config_service.get_llm_providers()
            test_prov = next(
                (p for p in providers if p.name == TEST_PROVIDER_NAME), None
            )

            if test_prov:
                print(f"   API Key: {_mask_key(test_prov.api_key)}")
                print(f"   来源: {test_prov.extra_config.get('source', 'unknown')}")
                print(f"   已配置: {test_prov.extra_config.get('has_api_key', False)}")
        else:
            print("❌ API Key 清空失败")
        return success

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback.print_exc()
        return False


async def cleanup_provider(provider_id: str):
    """清理测试数据"""
    # 初始化数据库
    await init_db()

    config_service = ConfigService()

    print("\n" + "=" * 80)
    print("🧹 清理测试数据")
    print("=" * 80)

    try:
        success = await config_service.delete_llm_provider(provider_id)
        if success:
            print("✅ 测试厂家删除成功")
        else:
            print("❌ 测试厂家删除失败")
        return success
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False


def _mask_key(key: str) -> str:
    """脱敏显示 API Key"""
    if not key:
        return "未配置"
    if len(key) <= 10:
        return "***"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


async def main():
    """主函数"""
    try:
        # 测试 1: 添加新厂家并配置 API Key
        provider_id = await add_provider_with_key()

        if not provider_id:
            print("\n❌ 测试 1 失败，终止后续测试")
            return

        # 测试 2: 更新厂家的 API Key
        await update_provider_key(provider_id)

        # 测试 3: 清空厂家的 API Key
        await clear_provider_key(provider_id)

        # 清理测试数据
        await cleanup_provider(provider_id)

        print("\n" + "=" * 80)
        print("✅ 所有测试完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        sys.exit(1)


async def test_api_key_edit_flow():
    provider_id = await add_provider_with_key()
    assert provider_id, "测试厂家创建失败"

    try:
        assert await update_provider_key(provider_id), "API Key 更新失败"
        assert await clear_provider_key(provider_id), "API Key 清空失败"
    finally:
        assert await cleanup_provider(provider_id), "测试厂家清理失败"


if __name__ == "__main__":
    asyncio.run(main())
