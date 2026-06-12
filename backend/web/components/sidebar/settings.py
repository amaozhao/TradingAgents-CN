import streamlit as st

from app.core.config import settings

from ...utils.auth import auth
from .common import get_version


def render_advanced_settings():
    with st.expander("⚙️ 高级设置"):
        enable_memory = st.checkbox(
            "启用记忆功能", value=False, help="启用智能体记忆功能（可能影响性能）"
        )

        enable_debug = st.checkbox(
            "调试模式", value=False, help="启用详细的调试信息输出"
        )

        max_tokens = st.slider(
            "最大输出长度",
            min_value=1000,
            max_value=8000,
            value=4000,
            step=500,
            help="AI模型的最大输出token数量",
        )

    return enable_memory, enable_debug, max_tokens


def validate_api_key(key, expected_format):
    """验证API密钥格式"""
    if not key:
        return "未配置", "error"

    if expected_format == "dashscope" and key.startswith("sk-") and len(key) >= 32:
        return f"{key[:8]}...", "success"
    elif expected_format == "deepseek" and key.startswith("sk-") and len(key) >= 32:
        return f"{key[:8]}...", "success"
    elif expected_format == "finnhub" and len(key) >= 20:
        return f"{key[:8]}...", "success"
    elif expected_format == "tushare" and len(key) >= 32:
        return f"{key[:8]}...", "success"
    elif expected_format == "google" and key.startswith("AIza") and len(key) >= 32:
        return f"{key[:8]}...", "success"
    elif expected_format == "openai" and key.startswith("sk-") and len(key) >= 40:
        return f"{key[:8]}...", "success"
    elif expected_format == "anthropic" and key.startswith("sk-") and len(key) >= 40:
        return f"{key[:8]}...", "success"
    elif expected_format == "reddit" and len(key) >= 10:
        return f"{key[:8]}...", "success"
    else:
        return f"{key[:8]}... (格式异常)", "warning"


def render_api_key_status():
    st.markdown("---")
    st.markdown("**🔧 系统配置**")
    st.markdown("**🔑 API密钥状态**")
    st.markdown("*必需配置:*")
    dashscope_key = settings.DASHSCOPE_API_KEY
    status, level = validate_api_key(dashscope_key, "dashscope")
    if level == "success":
        st.success(f"✅ 阿里百炼: {status}")
    elif level == "warning":
        st.warning(f"⚠️ 阿里百炼: {status}")
    else:
        st.error("❌ 阿里百炼: 未配置")
    finnhub_key = settings.FINNHUB_API_KEY
    status, level = validate_api_key(finnhub_key, "finnhub")
    if level == "success":
        st.success(f"✅ FinnHub: {status}")
    elif level == "warning":
        st.warning(f"⚠️ FinnHub: {status}")
    else:
        st.error("❌ FinnHub: 未配置")
    st.markdown("*可选配置:*")
    deepseek_key = settings.DEEPSEEK_API_KEY
    status, level = validate_api_key(deepseek_key, "deepseek")
    if level == "success":
        st.success(f"✅ DeepSeek: {status}")
    elif level == "warning":
        st.warning(f"⚠️ DeepSeek: {status}")
    else:
        st.info("ℹ️ DeepSeek: 未配置")
    tushare_key = settings.TUSHARE_TOKEN
    status, level = validate_api_key(tushare_key, "tushare")
    if level == "success":
        st.success(f"✅ Tushare: {status}")
    elif level == "warning":
        st.warning(f"⚠️ Tushare: {status}")
    else:
        st.info("ℹ️ Tushare: 未配置")
    google_key = settings.GOOGLE_API_KEY
    status, level = validate_api_key(google_key, "google")
    if level == "success":
        st.success(f"✅ Google AI: {status}")
    elif level == "warning":
        st.warning(f"⚠️ Google AI: {status}")
    else:
        st.info("ℹ️ Google AI: 未配置")
    openai_key = settings.OPENAI_API_KEY
    if openai_key and openai_key != "your_openai_api_key_here":
        status, level = validate_api_key(openai_key, "openai")
        if level == "success":
            st.success(f"✅ OpenAI: {status}")
        elif level == "warning":
            st.warning(f"⚠️ OpenAI: {status}")
    anthropic_key = settings.ANTHROPIC_API_KEY
    if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
        status, level = validate_api_key(anthropic_key, "anthropic")
        if level == "success":
            st.success(f"✅ Anthropic: {status}")
        elif level == "warning":
            st.warning(f"⚠️ Anthropic: {status}")


def render_system_sections():
    st.markdown("---")
    st.markdown("**ℹ️ 系统信息**")
    st.info(f"""
    **版本**: {get_version()}
    **框架**: Streamlit + LangGraph
    **AI模型**: {st.session_state.llm_provider.upper()} - {st.session_state.llm_model}
    **数据源**: Tushare + FinnHub API
    """)
    if auth and auth.check_permission("admin"):
        st.markdown("---")
        st.markdown("### 🔧 管理功能")

        if st.button(
            "📊 用户活动记录", key="user_activity_btn", use_container_width=True
        ):
            st.session_state.page = "user_activity"

        if st.button("⚙️ 系统设置", key="system_settings_btn", use_container_width=True):
            st.session_state.page = "system_settings"
    st.markdown("**📚 帮助资源**")
    st.markdown("""
    - [📖 使用文档](https://github.com/TauricResearch/TradingAgents)
    - [🐛 问题反馈](https://github.com/TauricResearch/TradingAgents/issues)
    - [💬 讨论社区](https://github.com/TauricResearch/TradingAgents/discussions)
    - [🔧 API密钥配置](../docs/configuration/google-ai-setup.md)
    """)
