#!/usr/bin/env python3
"""
快速测试脚本 - 验证API架构升级是否正常工作
"""

import asyncio
import importlib
import json
import sys
import time


async def test_database_connections():
    """测试数据库连接"""
    print("🔗 测试数据库连接...")

    try:
        init_database = getattr(
            importlib.import_module("app.core.database"), "init_database"
        )
        close_database = getattr(
            importlib.import_module("app.core.database"), "close_database"
        )
        get_database_health = getattr(
            importlib.import_module("app.core.database"), "get_database_health"
        )
        init_redis = getattr(importlib.import_module("app.core.redis"), "init_redis")
        close_redis = getattr(importlib.import_module("app.core.redis"), "close_redis")

        # 初始化连接
        await init_database()
        await init_redis()

        # 检查健康状态
        health = await get_database_health()
        print("📊 数据库健康状态:")
        print(json.dumps(health, indent=2, ensure_ascii=False))

        # 清理连接
        await close_database()
        await close_redis()

        return True

    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        return False


async def test_queue_service():
    """测试队列服务"""
    print("\n📋 测试队列服务...")

    try:
        init_database = getattr(
            importlib.import_module("app.core.database"), "init_database"
        )
        close_database = getattr(
            importlib.import_module("app.core.database"), "close_database"
        )
        init_redis = getattr(importlib.import_module("app.core.redis"), "init_redis")
        close_redis = getattr(importlib.import_module("app.core.redis"), "close_redis")
        get_queue_service = getattr(
            importlib.import_module("app.services.queue.service"), "get_queue_service"
        )

        # 初始化连接
        await init_database()
        await init_redis()

        queue_service = get_queue_service()

        # 测试入队
        task_id = await queue_service.enqueue_task(
            user_id="test_user", symbol="TEST001", params={"test": True}, priority=1
        )
        print(f"✅ 任务已入队: {task_id}")

        # 测试统计
        stats = await queue_service.stats()
        print(f"📊 队列统计: {json.dumps(stats, ensure_ascii=False)}")

        # 测试出队
        task_data = await queue_service.dequeue_task("test_worker")
        if task_data:
            print(f"✅ 任务已出队: {task_data['id']}")

            # 确认完成
            await queue_service.ack_task(task_data["id"], success=True)
            print("✅ 任务已确认完成")

        # 清理连接
        await close_database()
        await close_redis()

        return True

    except Exception as e:
        print(f"❌ 队列服务测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        return False


async def test_analysis_service():
    """测试分析服务"""
    print("\n🧠 测试分析服务...")

    try:
        init_database = getattr(
            importlib.import_module("app.core.database"), "init_database"
        )
        close_database = getattr(
            importlib.import_module("app.core.database"), "close_database"
        )
        init_redis = getattr(importlib.import_module("app.core.redis"), "init_redis")
        close_redis = getattr(importlib.import_module("app.core.redis"), "close_redis")
        analysis_service = getattr(
            importlib.import_module("app.services.analysis.service"), "analysis_service"
        )
        SingleAnalysisRequest = getattr(
            importlib.import_module("app.models.analysis"), "SingleAnalysisRequest"
        )
        AnalysisParameters = getattr(
            importlib.import_module("app.models.analysis"), "AnalysisParameters"
        )

        # 初始化连接
        await init_database()
        await init_redis()

        # 创建分析请求
        request = SingleAnalysisRequest(
            stock_code="TEST001",
            parameters=AnalysisParameters(
                research_depth="快速", selected_analysts=["基本面分析师"]
            ),
        )

        # 提交分析任务
        result = await analysis_service.submit_single_analysis("test_user", request)
        print(f"✅ 分析任务已提交: {json.dumps(result, ensure_ascii=False)}")

        # 检查任务状态
        task_id = result.get("task_id")
        if task_id:
            status = await analysis_service.get_task_status(task_id)
            print(f"📊 任务状态: {json.dumps(status, ensure_ascii=False)}")

        # 清理连接
        await close_database()
        await close_redis()

        return True

    except Exception as e:
        print(f"❌ 分析服务测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        return False


async def test_api_imports():
    """测试API模块导入"""
    print("\n📦 测试API模块导入...")

    try:
        # 测试核心模块
        getattr(importlib.import_module("app.core.config"), "settings")
        getattr(importlib.import_module("app.core.database"), "DatabaseManager")
        getattr(importlib.import_module("app.core.redis"), "RedisService")
        print("✅ 核心模块导入成功")

        # 测试服务模块
        getattr(importlib.import_module("app.services.queue.service"), "QueueService")
        getattr(
            importlib.import_module("app.services.analysis.service"), "AnalysisService"
        )
        print("✅ 服务模块导入成功")

        # 测试模型模块
        getattr(importlib.import_module("app.models.user"), "User")
        getattr(importlib.import_module("app.models.user"), "UserCreate")
        getattr(importlib.import_module("app.models.analysis"), "AnalysisTask")
        getattr(importlib.import_module("app.models.analysis"), "AnalysisBatch")
        print("✅ 模型模块导入成功")

        # 测试路由模块
        getattr(importlib.import_module("app.routers"), "analysis")
        getattr(importlib.import_module("app.routers"), "auth")
        getattr(importlib.import_module("app.routers"), "health")
        getattr(importlib.import_module("app.routers"), "queue")
        print("✅ 路由模块导入成功")

        # 测试中间件模块
        getattr(
            importlib.import_module("app.middleware.errors"), "ErrorHandlerMiddleware"
        )
        getattr(
            importlib.import_module("app.middleware.requests"), "RequestIDMiddleware"
        )
        getattr(importlib.import_module("app.middleware.limits"), "RateLimitMiddleware")
        print("✅ 中间件模块导入成功")

        return True

    except Exception as e:
        print(f"❌ 模块导入测试失败: {e}")
        traceback = importlib.import_module("traceback")
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("🧪 TradingAgents-CN v0.1.16 API架构快速测试")
    print("=" * 60)

    tests = [
        ("模块导入", test_api_imports),
        ("数据库连接", test_database_connections),
        ("队列服务", test_queue_service),
        ("分析服务", test_analysis_service),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🔍 开始测试: {test_name}")
        start_time = time.time()

        try:
            success = await test_func()
            elapsed = time.time() - start_time

            if success:
                print(f"✅ {test_name} 测试通过 ({elapsed:.2f}s)")
                results.append((test_name, True, elapsed))
            else:
                print(f"❌ {test_name} 测试失败 ({elapsed:.2f}s)")
                results.append((test_name, False, elapsed))

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"💥 {test_name} 测试异常: {e} ({elapsed:.2f}s)")
            results.append((test_name, False, elapsed))

    # 输出测试结果摘要
    print("\n" + "=" * 60)
    print("📊 测试结果摘要:")

    passed = 0
    total = len(results)

    for test_name, success, elapsed in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status} {test_name} ({elapsed:.2f}s)")
        if success:
            passed += 1

    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！API架构升级成功！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置和依赖")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
