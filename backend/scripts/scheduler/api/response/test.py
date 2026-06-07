"""
测试定时任务 API 响应格式
验证返回的数据结构是否正确
"""

import json

import requests
from app.core.config import settings

# 配置
BASE_URL = settings.TRADING_AGENTS_API_BASE_URL.rstrip("/")
USERNAME = (
    settings.TRADING_AGENTS_API_USERNAME
    or settings.TRADING_AGENTS_TEST_USERNAME
    or "admin"
)
PASSWORD = (
    settings.TRADING_AGENTS_API_PASSWORD
    or settings.TRADING_AGENTS_TEST_PASSWORD
    or "admin123"
)


def login() -> str:
    """登录并获取 token"""
    if settings.TRADING_AGENTS_API_TOKEN:
        return settings.TRADING_AGENTS_API_TOKEN

    print("🔐 正在登录...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            token = data["data"]["access_token"]
            print("✅ 登录成功")
            return token

    print("❌ 登录失败")
    return None


def check_jobs_response(token: str):
    """测试任务列表响应格式"""
    print("\n📋 测试任务列表响应格式...")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.get(f"{BASE_URL}/api/scheduler/jobs", headers=headers)

    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")

    if response.status_code == 200:
        data = response.json()
        print("\n响应体结构:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # 检查响应格式
        print("\n✅ 响应格式检查:")
        print(f"  - success: {data.get('success')}")
        print(f"  - message: {data.get('message')}")
        print(f"  - data 类型: {type(data.get('data'))}")

        if isinstance(data.get("data"), list):
            print(f"  - data 长度: {len(data.get('data'))}")
            if len(data.get("data")) > 0:
                print("\n第一个任务的结构:")
                print(json.dumps(data["data"][0], indent=2, ensure_ascii=False))
        else:
            print(f"  ⚠️ data 不是数组！实际类型: {type(data.get('data'))}")
            print(f"  实际内容: {data.get('data')}")
    else:
        print(f"❌ 请求失败: {response.text}")
    return response.status_code == 200


def check_stats_response(token: str):
    """测试统计信息响应格式"""
    print("\n📊 测试统计信息响应格式...")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.get(f"{BASE_URL}/api/scheduler/stats", headers=headers)

    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("\n响应体结构:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # 检查响应格式
        print("\n✅ 响应格式检查:")
        print(f"  - success: {data.get('success')}")
        print(f"  - message: {data.get('message')}")
        print(f"  - data 类型: {type(data.get('data'))}")

        if isinstance(data.get("data"), dict):
            stats = data.get("data")
            print(f"  - total_jobs: {stats.get('total_jobs')}")
            print(f"  - running_jobs: {stats.get('running_jobs')}")
            print(f"  - paused_jobs: {stats.get('paused_jobs')}")
        else:
            print(f"  ⚠️ data 不是对象！实际类型: {type(data.get('data'))}")
    else:
        print(f"❌ 请求失败: {response.text}")
    return response.status_code == 200


def main():
    """主函数"""
    print("=" * 60)
    print("🧪 定时任务 API 响应格式测试")
    print("=" * 60)

    # 1. 登录
    token = login()
    if not token:
        print("\n❌ 登录失败，无法继续测试")
        return False

    # 2. 测试任务列表响应
    jobs_ok = check_jobs_response(token)

    # 3. 测试统计信息响应
    stats_ok = check_stats_response(token)

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    return bool(jobs_ok and stats_ok)


def test_scheduler_api_response_flow():
    assert main()


if __name__ == "__main__":
    main()
