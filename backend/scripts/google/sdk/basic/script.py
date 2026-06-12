"""手动验证 Google AI SDK 的基础功能。"""

import importlib
import traceback
from typing import Callable

from app.core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI


def _run_case(name: str, fn: Callable[[str], None], google_api_key: str) -> None:
    print(f"📊 {name}")
    print("-" * 80)
    try:
        fn(google_api_key)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        traceback.print_exc()
    print()


def _test_google_sdk(google_api_key: str) -> None:
    genai = importlib.import_module("google.generativeai")
    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    print(f"✅ 模型创建成功: {model.model_name}")
    print("📤 发送测试消息: 你好，请用一句话介绍你自己")
    response = model.generate_content("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.text[:200]}...")


def _test_langchain_default(google_api_key: str) -> None:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=google_api_key,
        temperature=0.7,
        max_tokens=100,
    )
    print(f"✅ LLM 创建成功: {llm.model}")
    print("📤 发送测试消息: 你好，请用一句话介绍你自己")
    response = llm.invoke("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.content[:200]}...")


def _test_langchain_rest(google_api_key: str) -> None:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=google_api_key,
        temperature=0.7,
        max_tokens=100,
        transport="rest",
    )
    print(f"✅ LLM 创建成功: {llm.model}")
    print("   传输模式: REST")
    response = llm.invoke("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.content[:200]}...")


def _test_langchain_client_options(google_api_key: str) -> None:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=google_api_key,
        temperature=0.7,
        max_tokens=100,
        transport="rest",
        client_options={"api_endpoint": "https://generativelanguage.googleapis.com"},
    )
    print(f"✅ LLM 创建成功: {llm.model}")
    print("   自定义端点: https://generativelanguage.googleapis.com")
    response = llm.invoke("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.content[:200]}...")


def _test_project_adapter_default(google_api_key: str) -> None:
    from trader.llm.adapters import ChatGoogleOpenAI

    llm = ChatGoogleOpenAI(
        model="gemini-2.5-flash",
        google_api_key=google_api_key,
        temperature=0.7,
        max_tokens=100,
        transport="rest",
    )
    print(f"✅ LLM 创建成功: {llm.model}")
    response = llm.invoke("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.content[:200]}...")


def _test_project_adapter_base_url(google_api_key: str) -> None:
    from trader.llm.adapters import ChatGoogleOpenAI

    llm = ChatGoogleOpenAI(
        model="gemini-2.5-flash",
        google_api_key=google_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        temperature=0.7,
        max_tokens=100,
        transport="rest",
    )
    print(f"✅ LLM 创建成功: {llm.model}")
    response = llm.invoke("你好，请用一句话介绍你自己")
    print("✅ API 调用成功！")
    print(f"📥 响应: {response.content[:200]}...")


def main() -> int:
    print("=" * 80)
    print("🧪 Google AI SDK 基础功能测试")
    print("=" * 80)
    print()

    google_api_key = settings.GOOGLE_API_KEY
    if not google_api_key:
        print("❌ 错误：未找到 GOOGLE_API_KEY 配置")
        print("   请在 backend/.env 文件中设置 GOOGLE_API_KEY")
        return 1

    print(f"✅ 找到 GOOGLE_API_KEY: {google_api_key[:10]}...")
    print()

    cases = [
        ("测试 1: 直接使用 google-generativeai SDK", _test_google_sdk),
        (
            "测试 2: 使用 langchain_google_genai.ChatGoogleGenerativeAI",
            _test_langchain_default,
        ),
        ("测试 3: 使用 langchain_google_genai + REST 模式", _test_langchain_rest),
        (
            "测试 4: 使用 langchain_google_genai + 自定义 client_options",
            _test_langchain_client_options,
        ),
        (
            "测试 5: 使用我们的 ChatGoogleOpenAI 适配器（不提供 base_url）",
            _test_project_adapter_default,
        ),
        (
            "测试 6: 使用我们的 ChatGoogleOpenAI 适配器（提供 base_url）",
            _test_project_adapter_base_url,
        ),
    ]

    for name, fn in cases:
        _run_case(name, fn, google_api_key)

    print("=" * 80)
    print("🎉 测试完成！")
    print("=" * 80)
    print()
    print("📝 说明：")
    print("   - 测试 1-3 验证基础 SDK 功能")
    print("   - 测试 4 验证自定义 client_options")
    print("   - 测试 5-6 验证我们的适配器")
    print()
    print("💡 如果某个测试失败，请检查：")
    print("   1. 网络连接（需要能访问 Google API）")
    print("   2. GOOGLE_API_KEY 是否正确")
    print("   3. API 配额是否充足")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
