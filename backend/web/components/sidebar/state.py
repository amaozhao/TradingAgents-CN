import streamlit as st

from ...utils.persistence import load_model_selection, save_model_selection
from .common import logger


def render_storage_reader():
    st.markdown(
        """
    <div id="localStorage-reader" style="display: none;">
        <script>
        // 从localStorage读取设置并发送给Streamlit
        const provider = loadFromLocalStorage('llm_provider', 'dashscope');
        const category = loadFromLocalStorage('model_category', 'openai');
        const model = loadFromLocalStorage('llm_model', '');

        // 通过自定义事件发送数据
        window.parent.postMessage({
            type: 'localStorage_data',
            provider: provider,
            category: category,
            model: model
        }, '*');
        </script>
    </div>
    """,
        unsafe_allow_html=True,
    )


def restore_model_state():
    saved_config = load_model_selection()
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = saved_config["provider"]
        logger.debug(
            f"🔧 [Persistence] 恢复 llm_provider: {st.session_state.llm_provider}"
        )
    if "model_category" not in st.session_state:
        st.session_state.model_category = saved_config["category"]
        logger.debug(
            f"🔧 [Persistence] 恢复 model_category: {st.session_state.model_category}"
        )
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = saved_config["model"]
        logger.debug(f"🔧 [Persistence] 恢复 llm_model: {st.session_state.llm_model}")
    logger.debug(
        f"🔍 [Session State] 当前状态 - provider: {st.session_state.llm_provider}, category: {st.session_state.model_category}, model: {st.session_state.llm_model}"
    )
    st.markdown("### 🧠 AI模型配置")


def select_llm_provider():
    llm_provider = st.selectbox(
        "LLM提供商",
        options=[
            "dashscope",
            "deepseek",
            "google",
            "openai",
            "openrouter",
            "siliconflow",
            "custom_openai",
            "qianfan",
        ],
        index=[
            "dashscope",
            "deepseek",
            "google",
            "openai",
            "openrouter",
            "siliconflow",
            "custom_openai",
            "qianfan",
        ].index(st.session_state.llm_provider)
        if st.session_state.llm_provider
        in [
            "dashscope",
            "deepseek",
            "google",
            "openai",
            "openrouter",
            "siliconflow",
            "custom_openai",
            "qianfan",
        ]
        else 0,
        format_func=lambda x: {
            "dashscope": "🇨🇳 阿里百炼",
            "deepseek": "🚀 DeepSeek V3",
            "google": "🌟 Google AI",
            "openai": "🤖 OpenAI",
            "openrouter": "🌐 OpenRouter",
            "siliconflow": "🇨🇳 硅基流动",
            "custom_openai": "🔧 自定义OpenAI端点",
            "qianfan": "🧠 文心一言（千帆）",
        }[x],
        help="选择AI模型提供商",
        key="llm_provider_select",
    )

    return llm_provider


def persist_provider_choice(llm_provider):
    if st.session_state.llm_provider != llm_provider:
        logger.info(
            f"🔄 [Persistence] 提供商变更: {st.session_state.llm_provider} → {llm_provider}"
        )
        st.session_state.llm_provider = llm_provider
        # 提供商变更时清空模型选择
        st.session_state.llm_model = ""
        st.session_state.model_category = "openai"  # 重置为默认类别
        logger.info("🔄 [Persistence] 清空模型选择")

        # 保存到持久化存储
        save_model_selection(llm_provider, st.session_state.model_category, "")
    else:
        st.session_state.llm_provider = llm_provider
