# ruff: noqa: F403,F405
from .common import *


def render_openai_model_options():
    openai_options = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ]
    current_index = 0
    if st.session_state.llm_model in openai_options:
        current_index = openai_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择OpenAI模型",
        options=openai_options,
        index=current_index,
        format_func=lambda x: {
            "gpt-4o": "GPT-4o - 最新旗舰模型",
            "gpt-4o-mini": "GPT-4o Mini - 轻量旗舰",
            "gpt-4-turbo": "GPT-4 Turbo - 强化版",
            "gpt-4": "GPT-4 - 经典版",
            "gpt-3.5-turbo": "GPT-3.5 Turbo - 经济版",
        }[x],
        help="选择用于分析的OpenAI模型",
        key="openai_model_select",
    )
    st.markdown("**快速选择:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 GPT-4o", key="quick_gpt4o", use_container_width=True):
            model_id = "gpt-4o"
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择GPT-4o: {model_id}")
            st.rerun()
    with col2:
        if st.button(
            "⚡ GPT-4o Mini", key="quick_gpt4o_mini", use_container_width=True
        ):
            model_id = "gpt-4o-mini"
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择GPT-4o Mini: {model_id}")
            st.rerun()
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] OpenAI模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] OpenAI模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )
    st.info("💡 **OpenAI配置**: 在.env文件中设置OPENAI_API_KEY")


def render_custom_model_options():
    st.markdown("### 🔧 自定义OpenAI端点配置")
    if "custom_openai_base_url" not in st.session_state:
        st.session_state.custom_openai_base_url = "https://api.openai.com/v1"
    if "custom_openai_api_key" not in st.session_state:
        st.session_state.custom_openai_api_key = ""
    base_url = st.text_input(
        "API端点URL",
        value=st.session_state.custom_openai_base_url,
        placeholder="https://api.openai.com/v1",
        help="输入OpenAI兼容的API端点URL，例如中转服务或本地部署的API",
        key="custom_openai_base_url_input",
    )
    st.session_state.custom_openai_base_url = base_url
    api_key = st.text_input(
        "API密钥",
        value=st.session_state.custom_openai_api_key,
        type="password",
        placeholder="sk-...",
        help="输入API密钥，也可以在.env文件中设置CUSTOM_OPENAI_API_KEY",
        key="custom_openai_api_key_input",
    )
    st.session_state.custom_openai_api_key = api_key
    custom_openai_options = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "claude-3.5-sonnet",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "gemini-pro",
        "gemini-1.5-pro",
        "llama-3.1-8b",
        "llama-3.1-70b",
        "llama-3.1-405b",
        "custom-model",
    ]
    current_index = 0
    if st.session_state.llm_model in custom_openai_options:
        current_index = custom_openai_options.index(st.session_state.llm_model)
    llm_model = st.selectbox(
        "选择模型",
        options=custom_openai_options,
        index=current_index,
        format_func=lambda x: {
            "gpt-4o": "GPT-4o - OpenAI最新旗舰",
            "gpt-4o-mini": "GPT-4o Mini - 轻量旗舰",
            "gpt-4-turbo": "GPT-4 Turbo - 强化版",
            "gpt-4": "GPT-4 - 经典版",
            "gpt-3.5-turbo": "GPT-3.5 Turbo - 经济版",
            "claude-3.5-sonnet": "Claude 3.5 Sonnet - Anthropic旗舰",
            "claude-3-opus": "Claude 3 Opus - 强大性能",
            "claude-3-sonnet": "Claude 3 Sonnet - 平衡版",
            "claude-3-haiku": "Claude 3 Haiku - 快速版",
            "gemini-pro": "Gemini Pro - Google AI",
            "gemini-1.5-pro": "Gemini 1.5 Pro - 增强版",
            "llama-3.1-8b": "Llama 3.1 8B - Meta开源",
            "llama-3.1-70b": "Llama 3.1 70B - 大型开源",
            "llama-3.1-405b": "Llama 3.1 405B - 超大开源",
            "custom-model": "自定义模型名称",
        }[x],
        help="选择要使用的模型，支持各种OpenAI兼容的模型",
        key="custom_openai_model_select",
    )
    if llm_model == "custom-model":
        custom_model_name = st.text_input(
            "自定义模型名称",
            value="",
            placeholder="例如: gpt-4-custom, claude-3.5-sonnet-custom",
            help="输入自定义的模型名称",
            key="custom_model_name_input",
        )
        if custom_model_name:
            llm_model = custom_model_name
    if st.session_state.llm_model != llm_model:
        logger.debug(
            f"🔄 [Persistence] 自定义OpenAI模型变更: {st.session_state.llm_model} → {llm_model}"
        )
    st.session_state.llm_model = llm_model
    logger.debug(f"💾 [Persistence] 自定义OpenAI模型已保存: {llm_model}")
    save_model_selection(
        st.session_state.llm_provider,
        st.session_state.model_category,
        llm_model,
    )
    st.markdown("**🚀 常用端点快速配置:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "🌐 OpenAI官方",
            key="quick_openai_official",
            use_container_width=True,
        ):
            st.session_state.custom_openai_base_url = "https://api.openai.com/v1"
            st.rerun()

        if st.button(
            "🇨🇳 OpenAI中转1",
            key="quick_openai_relay1",
            use_container_width=True,
        ):
            st.session_state.custom_openai_base_url = "https://api.openai-proxy.com/v1"
            st.rerun()
    with col2:
        if st.button("🏠 本地部署", key="quick_local_deploy", use_container_width=True):
            st.session_state.custom_openai_base_url = "http://localhost:8000/v1"
            st.rerun()

        if st.button(
            "🇨🇳 OpenAI中转2",
            key="quick_openai_relay2",
            use_container_width=True,
        ):
            st.session_state.custom_openai_base_url = "https://api.openai-sb.com/v1"
            st.rerun()
    if base_url and api_key:
        st.success("✅ 配置完成")
        st.info(f"**端点**: `{base_url}`")
        st.info(f"**模型**: `{llm_model}`")
    elif base_url:
        st.warning("⚠️ 请输入API密钥")
    else:
        st.warning("⚠️ 请配置API端点URL和密钥")
    st.markdown("""
    **📖 配置说明:**
    - **API端点URL**: OpenAI兼容的API服务地址
    - **API密钥**: 对应服务的API密钥
    - **模型**: 选择或自定义模型名称

    **🔧 支持的服务类型:**
    - OpenAI官方API
    - OpenAI中转服务
    - 本地部署的OpenAI兼容服务
    - 其他兼容OpenAI格式的API服务
    """)


def render_openrouter_model_options():
    model_category = st.selectbox(
        "模型类别",
        options=["openai", "anthropic", "meta", "google", "custom"],
        index=["openai", "anthropic", "meta", "google", "custom"].index(
            st.session_state.model_category
        )
        if st.session_state.model_category
        in ["openai", "anthropic", "meta", "google", "custom"]
        else 0,
        format_func=lambda x: {
            "openai": "🤖 OpenAI (GPT系列)",
            "anthropic": "🧠 Anthropic (Claude系列)",
            "meta": "🦙 Meta (Llama系列)",
            "google": "🌟 Google (Gemini系列)",
            "custom": "✏️ 自定义模型",
        }[x],
        help="选择模型厂商类别或自定义输入",
        key="model_category_select",
    )
    if st.session_state.model_category != model_category:
        logger.debug(
            f"🔄 [Persistence] 模型类别变更: {st.session_state.model_category} → {model_category}"
        )
        st.session_state.llm_model = ""  # 类别变更时清空模型选择
    st.session_state.model_category = model_category
    save_model_selection(
        st.session_state.llm_provider,
        model_category,
        st.session_state.llm_model,
    )
    if model_category == "openai":
        openai_options = [
            "openai/o4-mini-high",
            "openai/o3-pro",
            "openai/o3-mini-high",
            "openai/o3-mini",
            "openai/o1-pro",
            "openai/o1-mini",
            "openai/gpt-4o-2024-11-20",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
        ]

        # 获取当前选择的索引
        current_index = 0
        if st.session_state.llm_model in openai_options:
            current_index = openai_options.index(st.session_state.llm_model)

        llm_model = st.selectbox(
            "选择OpenAI模型",
            options=openai_options,
            index=current_index,
            format_func=lambda x: {
                "openai/o4-mini-high": "🚀 o4 Mini High - 最新o4系列",
                "openai/o3-pro": "🚀 o3 Pro - 最新推理专业版",
                "openai/o3-mini-high": "o3 Mini High - 高性能推理",
                "openai/o3-mini": "o3 Mini - 推理模型",
                "openai/o1-pro": "o1 Pro - 专业推理",
                "openai/o1-mini": "o1 Mini - 轻量推理",
                "openai/gpt-4o-2024-11-20": "GPT-4o (2024-11-20) - 最新版",
                "openai/gpt-4o-mini": "GPT-4o Mini - 轻量旗舰",
                "openai/gpt-4-turbo": "GPT-4 Turbo - 经典强化",
                "openai/gpt-3.5-turbo": "GPT-3.5 Turbo - 经济实用",
            }[x],
            help="OpenAI公司的GPT和o系列模型，包含最新o4",
            key="openai_model_select",
        )

        # 更新session state和持久化存储
        if st.session_state.llm_model != llm_model:
            logger.debug(
                f"🔄 [Persistence] OpenAI模型变更: {st.session_state.llm_model} → {llm_model}"
            )
        st.session_state.llm_model = llm_model
        logger.debug(f"💾 [Persistence] OpenAI模型已保存: {llm_model}")

        # 保存到持久化存储
        save_model_selection(
            st.session_state.llm_provider,
            st.session_state.model_category,
            llm_model,
        )
    elif model_category == "anthropic":
        anthropic_options = [
            "anthropic/claude-opus-4",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-haiku-4",
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3.5-haiku",
            "anthropic/claude-3.5-sonnet-20241022",
            "anthropic/claude-3.5-haiku-20241022",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
        ]

        # 获取当前选择的索引
        current_index = 0
        if st.session_state.llm_model in anthropic_options:
            current_index = anthropic_options.index(st.session_state.llm_model)

        llm_model = st.selectbox(
            "选择Anthropic模型",
            options=anthropic_options,
            index=current_index,
            format_func=lambda x: {
                "anthropic/claude-opus-4": "🚀 Claude Opus 4 - 最新顶级模型",
                "anthropic/claude-sonnet-4": "🚀 Claude Sonnet 4 - 最新平衡模型",
                "anthropic/claude-haiku-4": "🚀 Claude Haiku 4 - 最新快速模型",
                "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet - 当前旗舰",
                "anthropic/claude-3.5-haiku": "Claude 3.5 Haiku - 快速响应",
                "anthropic/claude-3.5-sonnet-20241022": "Claude 3.5 Sonnet (2024-10-22)",
                "anthropic/claude-3.5-haiku-20241022": "Claude 3.5 Haiku (2024-10-22)",
                "anthropic/claude-3-opus": "Claude 3 Opus - 强大性能",
                "anthropic/claude-3-sonnet": "Claude 3 Sonnet - 平衡版",
                "anthropic/claude-3-haiku": "Claude 3 Haiku - 经济版",
            }[x],
            help="Anthropic公司的Claude系列模型，包含最新Claude 4",
            key="anthropic_model_select",
        )

        # 更新session state和持久化存储
        if st.session_state.llm_model != llm_model:
            logger.debug(
                f"🔄 [Persistence] Anthropic模型变更: {st.session_state.llm_model} → {llm_model}"
            )
        st.session_state.llm_model = llm_model
        logger.debug(f"💾 [Persistence] Anthropic模型已保存: {llm_model}")

        # 保存到持久化存储
        save_model_selection(
            st.session_state.llm_provider,
            st.session_state.model_category,
            llm_model,
        )
    elif model_category == "meta":
        meta_options = [
            "meta-llama/llama-4-maverick",
            "meta-llama/llama-4-scout",
            "meta-llama/llama-3.3-70b-instruct",
            "meta-llama/llama-3.2-90b-vision-instruct",
            "meta-llama/llama-3.1-405b-instruct",
            "meta-llama/llama-3.1-70b-instruct",
            "meta-llama/llama-3.2-11b-vision-instruct",
            "meta-llama/llama-3.1-8b-instruct",
            "meta-llama/llama-3.2-3b-instruct",
            "meta-llama/llama-3.2-1b-instruct",
        ]

        # 获取当前选择的索引
        current_index = 0
        if st.session_state.llm_model in meta_options:
            current_index = meta_options.index(st.session_state.llm_model)

        llm_model = st.selectbox(
            "选择Meta模型",
            options=meta_options,
            index=current_index,
            format_func=lambda x: {
                "meta-llama/llama-4-maverick": "🚀 Llama 4 Maverick - 最新旗舰",
                "meta-llama/llama-4-scout": "🚀 Llama 4 Scout - 最新预览",
                "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B - 强大性能",
                "meta-llama/llama-3.2-90b-vision-instruct": "Llama 3.2 90B Vision - 多模态",
                "meta-llama/llama-3.1-405b-instruct": "Llama 3.1 405B - 超大模型",
                "meta-llama/llama-3.1-70b-instruct": "Llama 3.1 70B - 平衡性能",
                "meta-llama/llama-3.2-11b-vision-instruct": "Llama 3.2 11B Vision - 轻量多模态",
                "meta-llama/llama-3.1-8b-instruct": "Llama 3.1 8B - 高效模型",
                "meta-llama/llama-3.2-3b-instruct": "Llama 3.2 3B - 轻量级",
                "meta-llama/llama-3.2-1b-instruct": "Llama 3.2 1B - 超轻量",
            }[x],
            help="Meta公司的Llama系列模型，包含最新Llama 4",
            key="meta_model_select",
        )

        # 更新session state和持久化存储
        if st.session_state.llm_model != llm_model:
            logger.debug(
                f"🔄 [Persistence] Meta模型变更: {st.session_state.llm_model} → {llm_model}"
            )
        st.session_state.llm_model = llm_model
        logger.debug(f"💾 [Persistence] Meta模型已保存: {llm_model}")

        # 保存到持久化存储
        save_model_selection(
            st.session_state.llm_provider,
            st.session_state.model_category,
            llm_model,
        )
    elif model_category == "google":
        google_openrouter_options = [
            "google/gemini-2.5-pro",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-flash-lite",
            "google/gemini-2.5-pro-002",
            "google/gemini-2.5-flash-002",
            "google/gemini-2.0-flash-001",
            "google/gemini-2.0-flash-lite-001",
            "google/gemini-1.5-pro",
            "google/gemini-1.5-flash",
            "google/gemma-3-27b-it",
            "google/gemma-3-12b-it",
            "google/gemma-2-27b-it",
        ]

        # 获取当前选择的索引
        current_index = 0
        if st.session_state.llm_model in google_openrouter_options:
            current_index = google_openrouter_options.index(st.session_state.llm_model)

        llm_model = st.selectbox(
            "选择Google模型",
            options=google_openrouter_options,
            index=current_index,
            format_func=lambda x: {
                "google/gemini-2.5-pro": "🚀 Gemini 2.5 Pro - 最新旗舰",
                "google/gemini-2.5-flash": "⚡ Gemini 2.5 Flash - 最新快速",
                "google/gemini-2.5-flash-lite": "💡 Gemini 2.5 Flash Lite - 轻量版",
                "google/gemini-2.5-pro-002": "🔧 Gemini 2.5 Pro-002 - 优化版",
                "google/gemini-2.5-flash-002": "⚡ Gemini 2.5 Flash-002 - 优化快速版",
                "google/gemini-2.0-flash-001": "Gemini 2.0 Flash - 稳定版",
                "google/gemini-2.0-flash-lite-001": "Gemini 2.0 Flash Lite",
                "google/gemini-1.5-pro": "Gemini 1.5 Pro - 专业版",
                "google/gemini-1.5-flash": "Gemini 1.5 Flash - 快速版",
                "google/gemma-3-27b-it": "Gemma 3 27B - 最新开源大模型",
                "google/gemma-3-12b-it": "Gemma 3 12B - 开源中型模型",
                "google/gemma-2-27b-it": "Gemma 2 27B - 开源经典版",
            }[x],
            help="Google公司的Gemini/Gemma系列模型，包含最新Gemini 2.5",
            key="google_openrouter_model_select",
        )

        # 更新session state和持久化存储
        if st.session_state.llm_model != llm_model:
            logger.debug(
                f"🔄 [Persistence] Google OpenRouter模型变更: {st.session_state.llm_model} → {llm_model}"
            )
        st.session_state.llm_model = llm_model
        logger.debug(f"💾 [Persistence] Google OpenRouter模型已保存: {llm_model}")

        # 保存到持久化存储
        save_model_selection(
            st.session_state.llm_provider,
            st.session_state.model_category,
            llm_model,
        )

    else:  # custom
        st.markdown("### ✏️ 自定义模型")

        # 初始化自定义模型session state
        if "custom_model" not in st.session_state:
            st.session_state.custom_model = ""

        # 自定义模型输入 - 使用session state作为默认值
        default_value = (
            st.session_state.custom_model
            if st.session_state.custom_model
            else "anthropic/claude-3.7-sonnet"
        )

        llm_model = st.text_input(
            "输入模型ID",
            value=default_value,
            placeholder="例如: anthropic/claude-3.7-sonnet",
            help="输入OpenRouter支持的任何模型ID",
            key="custom_model_input",
        )

        # 常用模型快速选择
        st.markdown("**快速选择常用模型:**")

        # 长条形按钮，每个占一行
        if st.button(
            "🧠 Claude 3.7 Sonnet - 最新对话模型",
            key="claude37",
            use_container_width=True,
        ):
            model_id = "anthropic/claude-3.7-sonnet"
            st.session_state.custom_model = model_id
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择Claude 3.7 Sonnet: {model_id}")
            st.rerun()

        if st.button(
            "💎 Claude 4 Opus - 顶级性能模型",
            key="claude4opus",
            use_container_width=True,
        ):
            model_id = "anthropic/claude-opus-4"
            st.session_state.custom_model = model_id
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择Claude 4 Opus: {model_id}")
            st.rerun()

        if st.button(
            "🤖 GPT-4o - OpenAI旗舰模型", key="gpt4o", use_container_width=True
        ):
            model_id = "openai/gpt-4o"
            st.session_state.custom_model = model_id
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择GPT-4o: {model_id}")
            st.rerun()

        if st.button(
            "🦙 Llama 4 Scout - Meta最新模型",
            key="llama4",
            use_container_width=True,
        ):
            model_id = "meta-llama/llama-4-scout"
            st.session_state.custom_model = model_id
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择Llama 4 Scout: {model_id}")
            st.rerun()

        if st.button(
            "🌟 Gemini 2.5 Pro - Google多模态",
            key="gemini25",
            use_container_width=True,
        ):
            model_id = "google/gemini-2.5-pro"
            st.session_state.custom_model = model_id
            st.session_state.llm_model = model_id
            save_model_selection(
                st.session_state.llm_provider,
                st.session_state.model_category,
                model_id,
            )
            logger.debug(f"💾 [Persistence] 快速选择Gemini 2.5 Pro: {model_id}")
            st.rerun()

        # 更新session state和持久化存储
        if st.session_state.llm_model != llm_model:
            logger.debug(
                f"🔄 [Persistence] 自定义模型变更: {st.session_state.llm_model} → {llm_model}"
            )
        st.session_state.custom_model = llm_model
        st.session_state.llm_model = llm_model
        logger.debug(f"💾 [Persistence] 自定义模型已保存: {llm_model}")

        # 保存到持久化存储
        save_model_selection(
            st.session_state.llm_provider,
            st.session_state.model_category,
            llm_model,
        )

        # 模型验证提示
        if llm_model:
            st.success(f"✅ 当前模型: `{llm_model}`")

            # 提供模型查找链接
            st.markdown("""
            **📚 查找更多模型:**
            - [OpenRouter模型列表](https://openrouter.ai/models)
            - [Anthropic模型文档](https://docs.anthropic.com/claude/docs/models-overview)
            - [OpenAI模型文档](https://platform.openai.com/docs/models)
            """)
        else:
            st.warning("⚠️ 请输入有效的模型ID")
    st.info(
        "💡 **OpenRouter配置**: 在.env文件中设置OPENROUTER_API_KEY，或者如果只用OpenRouter可以设置OPENAI_API_KEY"
    )
