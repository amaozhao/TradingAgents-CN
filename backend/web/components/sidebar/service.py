# ruff: noqa: F403,F405
from .assets import render_sidebar_assets
from .common import *
from .dispatch import render_model_options
from .settings import (
    render_advanced_settings,
    render_api_key_status,
    render_system_sections,
)
from .state import (
    persist_provider_choice,
    render_storage_reader,
    restore_model_state,
    select_llm_provider,
)


def render_sidebar():
    """渲染侧边栏配置"""
    render_sidebar_assets()

    with st.sidebar:
        render_storage_reader()
        restore_model_state()
        st.markdown("### 🧠 AI模型配置")
        llm_provider = select_llm_provider()
        persist_provider_choice(llm_provider)
        render_model_options(llm_provider)
        enable_memory, enable_debug, max_tokens = render_advanced_settings()
        render_api_key_status()
        render_system_sections()

    final_provider = st.session_state.llm_provider
    final_model = st.session_state.llm_model

    logger.debug(
        f"🔄 [Session State] 返回配置 - provider: {final_provider}, model: {final_model}"
    )

    return {
        "llm_provider": final_provider,
        "llm_model": final_model,
        "enable_memory": enable_memory,
        "enable_debug": enable_debug,
        "max_tokens": max_tokens,
    }
