# ruff: noqa: F403,F405
from .common import *


def render_dashscope_model_options():
    dashscope_options = ["qwen-turbo", "qwen-plus-latest", "qwen-max"]
    current_index = 1  # 默认选择qwen-plus-latest
    if st.session_state.llm_model in dashscope_options:
        current_index = dashscope_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "模型版本",
        options=dashscope_options,
        index=current_index,
        format_func=lambda x: {
            "qwen-turbo": "Turbo - 快速",
            "qwen-plus-latest": "Plus - 平衡",
            "qwen-max": "Max - 最强",
        }[x],
        help="选择用于分析的阿里百炼模型",
        key="dashscope_model_select",
    )
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] DashScope模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] DashScope模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )


def render_siliconflow_model_options():
    siliconflow_options = [
        "Qwen/Qwen3-30B-A3B-Thinking-2507",
        "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "deepseek-ai/DeepSeek-R1",
        "zai-org/GLM-4.5",
        "moonshotai/Kimi-K2-Instruct",
    ]
    current_index = 0
    if st.session_state.llm_model in siliconflow_options:
        current_index = siliconflow_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择siliconflow模型",
        options=siliconflow_options,
        index=current_index,
        format_func=lambda x: {
            "Qwen/Qwen3-30B-A3B-Thinking-2507": "Qwen3-30B-A3B-Thinking-2507 - 30B思维链模型",
            "Qwen/Qwen3-30B-A3B-Instruct-2507": "Qwen3-30B-A3B-Instruct-2507 - 30B指令模型",
            "Qwen/Qwen3-235B-A22B-Thinking-2507": "Qwen3-235B-A22B-Thinking-2507 - 235B思维链模型",
            "Qwen/Qwen3-235B-A22B-Instruct-2507": "Qwen3-235B-A22B-Instruct-2507 - 235B指令模型",
            "deepseek-ai/DeepSeek-R1": "DeepSeek-R1",
            "zai-org/GLM-4.5": "GLM-4.5 - 智谱",
            "moonshotai/Kimi-K2-Instruct": "Kimi-K2-Instruct",
        }[x],
        help="选择用于分析的siliconflow模型",
        key="siliconflow_model_select",
    )
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] siliconflow模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] siliconflow模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )


def render_deepseek_model_options():
    deepseek_options = ["deepseek-chat"]
    current_index = 0
    if st.session_state.llm_model in deepseek_options:
        current_index = deepseek_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择DeepSeek模型",
        options=deepseek_options,
        index=current_index,
        format_func=lambda x: {
            "deepseek-chat": "DeepSeek Chat - 通用对话模型，适合股票分析"
        }[x],
        help="选择用于分析的DeepSeek模型",
        key="deepseek_model_select",
    )
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] DeepSeek模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] DeepSeek模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )


def render_google_model_options():
    google_options = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro-002",
        "gemini-2.5-flash-002",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite-preview-06-17",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]
    current_index = 0
    if st.session_state.llm_model in google_options:
        current_index = google_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择Google模型",
        options=google_options,
        index=current_index,
        format_func=lambda x: {
            "gemini-2.5-pro": "Gemini 2.5 Pro - 🚀 最新旗舰模型",
            "gemini-2.5-flash": "Gemini 2.5 Flash - ⚡ 最新快速模型",
            "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite - 💡 轻量快速",
            "gemini-2.5-flash-lite-preview-06-17": "Gemini 2.5 Flash Lite Preview - ⚡ 超快响应 (1.45s)",
            "gemini-2.5-pro-002": "Gemini 2.5 Pro-002 - 🔧 优化版本",
            "gemini-2.5-flash-002": "Gemini 2.5 Flash-002 - ⚡ 优化快速版",
            "gemini-2.0-flash": "Gemini 2.0 Flash - 🚀 推荐使用 (1.87s)",
            "gemini-1.5-pro": "Gemini 1.5 Pro - ⚖️ 强大性能 (2.25s)",
            "gemini-1.5-flash": "Gemini 1.5 Flash - 💨 快速响应 (2.87s)",
        }[x],
        help="选择用于分析的Google Gemini模型",
        key="google_model_select",
    )
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] Google模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] Google模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )


def render_qianfan_model_options():
    qianfan_options = [
        "ernie-3.5-8k",
        "ernie-4.0-turbo-8k",
        "ERNIE-Speed-8K",
        "ERNIE-Lite-8K",
    ]
    current_index = 0
    if st.session_state.llm_model in qianfan_options:
        current_index = qianfan_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择文心一言模型",
        options=qianfan_options,
        index=current_index,
        format_func=lambda x: {
            "ernie-3.5-8k": "ERNIE 3.5 8K - ⚡ 快速高效",
            "ernie-4.0-turbo-8k": "ERNIE 4.0 Turbo 8K - 🚀 强大推理",
            "ERNIE-Speed-8K": "ERNIE Speed 8K - 🏃 极速响应",
            "ERNIE-Lite-8K": "ERNIE Lite 8K - 💡 轻量经济",
        }[x],
        help="选择用于分析的文心一言（千帆）模型",
        key="qianfan_model_select",
    )
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] Qianfan模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] Qianfan模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )
