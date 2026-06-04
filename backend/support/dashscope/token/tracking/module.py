#!/usr/bin/env python3
"""
测试DashScope适配器的token统计功能
"""

import importlib
import os
import time

from langchain_core.messages import HumanMessage

from trader.config.manager import config_manager, token_tracker
from trader.llm.adapters.dashscope.native import ChatDashScope


def test_dashscope_token_tracking():
    """测试DashScope适配器的token统计功能"""
    print("🧪 开始测试DashScope Token统计功能...")

    # 检查API密钥
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 未找到DASHSCOPE_API_KEY环境变量")
        print("请在.env文件中设置DASHSCOPE_API_KEY")
        return False

    try:
        # 初始化DashScope适配器
        print("📝 初始化DashScope适配器...")
        llm = ChatDashScope(
            model="qwen-turbo", api_key=api_key, temperature=0.7, max_tokens=500
        )

        # 获取初始统计
        initial_stats = config_manager.get_usage_statistics(1)
        initial_cost = initial_stats.get("total_cost", 0)
        initial_requests = initial_stats.get("total_requests", 0)

        print(f"📊 初始统计 - 成本: ¥{initial_cost:.4f}, 请求数: {initial_requests}")

        # 测试消息
        test_messages = [
            HumanMessage(content="请简单介绍一下股票投资的基本概念，不超过100字。")
        ]

        # 生成会话ID
        session_id = f"test_session_{int(time.time())}"

        print(f"🚀 发送测试请求 (会话ID: {session_id})...")

        # 调用LLM（传入session_id和analysis_type）
        response = llm.invoke(
            test_messages, session_id=session_id, analysis_type="test_analysis"
        )

        print(f"✅ 收到响应: {response.content[:100]}...")

        # 等待一下确保记录已保存
        time.sleep(1)

        # 获取更新后的统计
        updated_stats = config_manager.get_usage_statistics(1)
        updated_cost = updated_stats.get("total_cost", 0)
        updated_requests = updated_stats.get("total_requests", 0)

        print(f"📊 更新后统计 - 成本: ¥{updated_cost:.4f}, 请求数: {updated_requests}")

        # 检查是否有新的记录
        cost_increase = updated_cost - initial_cost
        requests_increase = updated_requests - initial_requests

        print(
            f"📈 变化 - 成本增加: ¥{cost_increase:.4f}, 请求增加: {requests_increase}"
        )

        # 验证结果
        if requests_increase > 0:
            print("✅ Token统计功能正常工作！")

            # 显示供应商统计
            provider_stats = updated_stats.get("provider_stats", {})
            dashscope_stats = provider_stats.get("dashscope", {})

            if dashscope_stats:
                print("📊 DashScope统计:")
                print(f"   - 成本: ¥{dashscope_stats.get('cost', 0):.4f}")
                print(f"   - 输入tokens: {dashscope_stats.get('input_tokens', 0)}")
                print(f"   - 输出tokens: {dashscope_stats.get('output_tokens', 0)}")
                print(f"   - 请求数: {dashscope_stats.get('requests', 0)}")

            # 测试会话成本查询
            session_cost = token_tracker.get_session_cost(session_id)
            print(f"💰 会话成本: ¥{session_cost:.4f}")

            return True
        else:
            print("❌ Token统计功能未正常工作")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        return False


def test_postgres_storage():
    """测试PostgreSQL token 存储功能"""
    print("\n🧪 测试PostgreSQL token 存储功能...")

    # 检查是否启用了 PostgreSQL token 存储
    use_postgres = os.getenv("USE_POSTGRES_STORAGE", "false").lower() == "true"

    if not use_postgres:
        print("ℹ️ PostgreSQL token 存储未启用，跳过 PostgreSQL token 存储测试")
        print(
            "要启用PostgreSQL token 存储，请在.env文件中设置 USE_POSTGRES_STORAGE=true"
        )
        return True

    # 检查PostgreSQL token 存储连接
    if (
        config_manager.postgres_storage
        and config_manager.postgres_storage.is_connected()
    ):
        print("✅ PostgreSQL token 存储连接正常")

        # 测试清理功能（清理超过1天的测试记录）
        try:
            deleted_count = config_manager.postgres_storage.cleanup_old_records(1)
            print(f"🧹 清理了 {deleted_count} 条旧的测试记录")
        except Exception as e:
            print(f"⚠️ 清理旧记录失败: {e}")

        return True
    else:
        print("❌ PostgreSQL token 存储连接失败")
        print("请检查 PostgreSQL 配置")
        return False


def main():
    """主测试函数"""
    print("🔬 DashScope Token统计和PostgreSQL token 存储测试")
    print("=" * 50)

    # 显示配置状态
    env_status = config_manager.get_env_config_status()
    print("📋 配置状态:")
    print(f"   - .env文件存在: {env_status['env_file_exists']}")
    print(f"   - DashScope API: {env_status['api_keys']['dashscope']}")

    # 检查 PostgreSQL token 存储配置
    use_postgres = (
        os.getenv(
            "USE_POSTGRES_STORAGE", os.getenv("USE_POSTGRES_STORAGE", "false")
        ).lower()
        == "true"
    )
    print(f"   - PostgreSQL token存储: {use_postgres}")

    if use_postgres:
        postgres_db = os.getenv("POSTGRES_DB", "trading_agents")
        print(f"   - PostgreSQL数据库: {postgres_db}")

    print("\n" + "=" * 50)

    # 运行测试
    success = True

    # 测试DashScope token统计
    if not test_dashscope_token_tracking():
        success = False

    # 测试PostgreSQL token 存储
    if not test_postgres_storage():
        success = False

    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试通过！")
    else:
        print("❌ 部分测试失败")

    return success


if __name__ == "__main__":
    main()
