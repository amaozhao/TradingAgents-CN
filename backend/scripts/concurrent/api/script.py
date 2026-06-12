"""
测试并发API请求，验证数据源测试时其他接口是否会超时
"""

import asyncio
import time
import traceback
from datetime import datetime

import aiohttp
from app.core.config import settings
from app.services.user import UserService

BASE_URL = settings.TRADING_AGENTS_API_BASE_URL.rstrip("/")
API_USERNAME = (
    settings.TRADING_AGENTS_API_USERNAME
    or settings.TRADING_AGENTS_TEST_USERNAME
    or "admin"
)
API_PASSWORD = (
    settings.TRADING_AGENTS_API_PASSWORD
    or settings.TRADING_AGENTS_TEST_PASSWORD
    or "admin123"
)
CONCURRENT_NOTIFICATION_INTERVAL_SECONDS = 0.5
MAX_CONCURRENT_NOTIFICATION_PROBES = 10
MIN_CONCURRENT_NOTIFICATION_PROBES = 2


async def ensure_api_user() -> None:
    """确保真实登录接口使用的测试管理员存在且密码匹配。"""
    user_service = UserService()
    existing_user = await user_service.get_user_by_username(API_USERNAME)

    if existing_user is None:
        created_user = await user_service.create_admin_user(
            username=API_USERNAME,
            password=API_PASSWORD,
            email=f"{API_USERNAME}@trader.local",
        )
        assert created_user, f"无法创建测试用户: {API_USERNAME}"
        return

    user_service.users_collection.update_one(
        {"username": API_USERNAME},
        {
            "$set": {
                "is_active": True,
                "is_admin": True,
                "hashed_password": user_service.hash_password(API_PASSWORD),
            }
        },
    )


async def get_auth_headers(session: aiohttp.ClientSession) -> dict[str, str]:
    if settings.TRADING_AGENTS_API_TOKEN:
        return {"Authorization": f"Bearer {settings.TRADING_AGENTS_API_TOKEN}"}

    await ensure_api_user()
    async with session.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": API_USERNAME, "password": API_PASSWORD},
        timeout=aiohttp.ClientTimeout(total=settings.TRADING_AGENTS_API_TIMEOUT),
    ) as response:
        response.raise_for_status()
        data = await response.json()
        token = data.get("data", {}).get("access_token")
        assert token, "登录接口没有返回 access_token"
        return {"Authorization": f"Bearer {token}"}


async def check_notifications_api(
    session: aiohttp.ClientSession, test_id: int, headers: dict[str, str]
):
    """测试通知接口"""
    url = f"{BASE_URL}/api/notifications/unread_count"

    start = time.time()
    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
        ) as response:
            elapsed = time.time() - start
            if response.status == 200:
                data = await response.json()
                print(f"  [{test_id:2d}] ✅ 通知接口响应成功 ({elapsed:.2f}秒): {data}")
                return True
            else:
                print(
                    f"  [{test_id:2d}] ❌ 通知接口返回错误 ({elapsed:.2f}秒): {response.status}"
                )
                return False
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"  [{test_id:2d}] ⏱️  通知接口超时 ({elapsed:.2f}秒)")
        return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [{test_id:2d}] ❌ 通知接口错误 ({elapsed:.2f}秒): {e}")
        return False


async def check_data_sources_api(session: aiohttp.ClientSession):
    """测试数据源测试接口"""
    url = f"{BASE_URL}/api/sync/multi-source/test-sources"

    start = time.time()
    try:
        async with session.post(
            url, timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            elapsed = time.time() - start
            if response.status == 200:
                data = await response.json()
                print(f"\n🧪 数据源测试完成 ({elapsed:.2f}秒)")
                if data.get("success") and "data" in data:
                    test_results = data["data"].get("test_results", [])
                    for result in test_results:
                        print(f"   📡 {result['name']}: ", end="")
                        stock_list = result.get("tests", {}).get("stock_list", {})
                        if stock_list.get("success"):
                            print(f"✅ {stock_list.get('count', 0)} 只股票")
                        else:
                            print(f"❌ {stock_list.get('message', 'Unknown error')}")
                return True
            else:
                print(f"\n❌ 数据源测试失败 ({elapsed:.2f}秒): {response.status}")
                return False
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"\n⏱️  数据源测试超时 ({elapsed:.2f}秒)")
        return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ 数据源测试错误 ({elapsed:.2f}秒): {e}")
        return False


async def concurrent_test():
    """并发测试：同时运行数据源测试和通知接口请求"""
    print("=" * 80)
    print("🚀 并发API测试")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print()

    async with aiohttp.ClientSession() as session:
        headers = await get_auth_headers(session)

        # 启动数据源测试
        print("📊 启动数据源测试...")
        data_source_task = asyncio.create_task(check_data_sources_api(session))

        # 数据源探测通常很快，通知探针必须覆盖数据源运行窗口，而不是在
        # 数据源结束后继续固定打满 10 秒，避免把无关的后续服务抖动算作并发失败。
        print("\n📬 开始并发测试通知接口（数据源运行窗口采样）...")
        print()

        notification_tasks = []
        for i in range(MAX_CONCURRENT_NOTIFICATION_PROBES):
            task = asyncio.create_task(check_notifications_api(session, i + 1, headers))
            notification_tasks.append(task)
            await asyncio.sleep(CONCURRENT_NOTIFICATION_INTERVAL_SECONDS)
            if (
                data_source_task.done()
                and len(notification_tasks) >= MIN_CONCURRENT_NOTIFICATION_PROBES
            ):
                break

        # 等待所有任务完成
        print("\n⏳ 等待所有任务完成...")
        all_results = await asyncio.gather(
            data_source_task, *notification_tasks, return_exceptions=True
        )

        # 统计结果
        data_source_success = (
            all_results[0] if not isinstance(all_results[0], Exception) else False
        )
        notification_results = [
            r for r in all_results[1:] if not isinstance(r, Exception)
        ]
        notification_success_count = sum(1 for r in notification_results if r)
        notification_total = len(notification_results)

        print()
        print("=" * 80)
        print("📊 测试结果汇总")
        print("=" * 80)
        print(f"⏰ 结束时间: {datetime.now().strftime('%H:%M:%S')}")
        print()
        print(f"🧪 数据源测试: {'✅ 成功' if data_source_success else '❌ 失败'}")
        print(
            f"📬 通知接口测试: {notification_success_count}/{notification_total} 成功"
        )
        print()

        if notification_success_count == notification_total:
            print("🎉 所有测试通过！数据源测试期间通知接口没有超时。")
        elif notification_success_count > 0:
            print(
                f"⚠️  部分测试失败：{notification_total - notification_success_count} 个请求失败"
            )
        else:
            print("❌ 所有通知接口请求都失败了！")

        print("=" * 80)
        return (
            bool(data_source_success)
            and notification_success_count == notification_total
        )


async def sequential_test():
    """顺序测试：先测试通知接口，再测试数据源"""
    print("\n" + "=" * 80)
    print("🔄 顺序测试（对照组）")
    print("=" * 80)
    print()

    async with aiohttp.ClientSession() as session:
        headers = await get_auth_headers(session)

        # 先测试通知接口
        print("📬 测试通知接口（数据源测试前）...")
        success = await check_notifications_api(session, 0, headers)
        print(f"   结果: {'✅ 成功' if success else '❌ 失败'}")
        print()

        # 再测试数据源
        print("🧪 测试数据源...")
        data_source_success = await check_data_sources_api(session)
        print()

        # 最后再测试通知接口
        print("📬 测试通知接口（数据源测试后）...")
        final_success = await check_notifications_api(session, 0, headers)
        print(f"   结果: {'✅ 成功' if final_success else '❌ 失败'}")
        print()
        return bool(success and data_source_success and final_success)


async def main():
    """主测试函数"""
    print("\n" + "🔬" * 40)
    print("并发API测试 - 验证数据源测试时其他接口是否会超时")
    print("🔬" * 40)
    print()
    print("📝 测试说明:")
    print("   1. 先进行顺序测试（对照组）")
    print("   2. 再进行并发测试（实验组）")
    print("   3. 验证修复后的代码是否解决了超时问题")
    print()

    # 顺序测试
    sequential_success = await sequential_test()

    # 等待3秒
    print("⏳ 等待3秒后开始并发测试...")
    await asyncio.sleep(3)

    # 并发测试
    concurrent_success = await concurrent_test()
    return bool(sequential_success and concurrent_success)


async def test_concurrent_api_flow():
    assert await main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试出错: {e}")
        traceback.print_exc()
