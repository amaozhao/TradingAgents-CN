# ruff: noqa: F403,F405
from .common import *


_trading_agents_logging_initialized = False
_data_source_manager = None


def _ensure_trading_agents_logging() -> None:
    global _trading_agents_logging_initialized
    if _trading_agents_logging_initialized:
        return

    init_logging = getattr(
        importlib.import_module("trader.utils.logging.init"), "init_logging"
    )

    init_logging()
    _trading_agents_logging_initialized = True


def _get_stock_info_safe(stock_code: str):
    """获取股票基础信息的安全封装，延迟加载数据源管理器。"""

    global _data_source_manager
    try:
        if _data_source_manager is None:
            get_data_source_manager = getattr(
                importlib.import_module("trader.flows.sources"),
                "get_data_source_manager",
            )

            _data_source_manager = get_data_source_manager()
        return _data_source_manager.get_stock_basic_info(stock_code)
    except Exception:
        return None


# 设置日志
logger = logging.getLogger("app.services.analysis.simple")

# 配置服务实例
config_service = ConfigService()


def _dual_write_analysis_task_sync(document: Dict[str, Any]) -> None:
    """Run PostgreSQL dual-write from analysis worker threads."""

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            dual_write_hot_document("analysis_tasks", document)
        )
        if result.status == "failed":
            logger.warning("⚠️ 分析任务 PostgreSQL 双写失败: %s", result.reason)
    except Exception as exc:
        logger.warning("⚠️ 分析任务 PostgreSQL 双写失败: %s", exc)
        raise
    finally:
        loop.close()


async def get_provider_by_model_name(model_name: str) -> str:
    """
    根据模型名称从数据库配置中查找对应的供应商（异步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        str: 供应商名称，如 'dashscope', 'openai' 等
    """
    try:
        # 从配置服务获取系统配置
        system_config = await config_service.get_system_config()
        if not system_config or not system_config.llm_configs:
            logger.warning("⚠️ 系统配置为空，使用默认供应商映射")
            return _get_default_provider_by_model(model_name)

        # 在LLM配置中查找匹配的模型
        for llm_config in system_config.llm_configs:
            if llm_config.model_name == model_name:
                provider = str(
                    getattr(llm_config.provider, "value", llm_config.provider)
                )
                logger.info(f"✅ 从数据库找到模型 {model_name} 的供应商: {provider}")
                return provider

        # 如果数据库中没有找到，使用默认映射
        logger.warning(f"⚠️ 数据库中未找到模型 {model_name}，使用默认映射")
        return _get_default_provider_by_model(model_name)

    except Exception as e:
        logger.error(f"❌ 查找模型供应商失败: {e}")
        return _get_default_provider_by_model(model_name)


def get_provider_by_model_name_sync(model_name: str) -> str:
    """
    根据模型名称从数据库配置中查找对应的供应商（同步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        str: 供应商名称，如 'dashscope', 'openai' 等
    """
    provider_info = get_provider_and_url_by_model_sync(model_name)
    return provider_info["provider"]


def get_provider_and_url_by_model_sync(model_name: str) -> dict:
    """
    根据模型名称从数据库配置中查找对应的供应商和 API URL（同步版本）

    Args:
        model_name: 模型名称，如 'qwen-turbo', 'gpt-4' 等

    Returns:
        dict: {"provider": "google", "backend_url": "https://...", "api_key": "xxx"}
    """
    try:
        # 使用同步 PostgreSQL 客户端直接查询
        get_postgres_db_sync = getattr(
            importlib.import_module("app.core.database"), "get_postgres_db_sync"
        )
        importlib.import_module("os")

        db = get_postgres_db_sync()

        # 查询最新的活跃配置
        configs_collection = db.system_configs
        doc = configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

        if doc and "llm_configs" in doc:
            llm_configs = doc["llm_configs"]

            for config_dict in llm_configs:
                if config_dict.get("model_name") == model_name:
                    provider = config_dict.get("provider")
                    api_base = config_dict.get("api_base")
                    model_api_key = config_dict.get(
                        "api_key"
                    )  # 🔥 获取模型配置的 API Key

                    # 从 llm_providers 集合中查找厂家配置
                    providers_collection = db.llm_providers
                    provider_doc = providers_collection.find_one({"name": provider})

                    # 🔥 确定 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
                    api_key = None
                    if (
                        model_api_key
                        and model_api_key.strip()
                        and model_api_key != "your-api-key"
                    ):
                        api_key = model_api_key
                        logger.info("✅ [同步查询] 使用模型配置的 API Key")
                    elif provider_doc and provider_doc.get("api_key"):
                        provider_api_key = provider_doc["api_key"]
                        if (
                            provider_api_key
                            and provider_api_key.strip()
                            and provider_api_key != "your-api-key"
                        ):
                            api_key = provider_api_key
                            logger.info("✅ [同步查询] 使用厂家配置的 API Key")

                    # 如果数据库中没有有效的 API Key，尝试从环境变量获取
                    if not api_key:
                        api_key = _get_env_api_key_for_provider(provider)
                        if api_key:
                            logger.info("✅ [同步查询] 使用环境变量的 API Key")
                        else:
                            logger.warning(f"⚠️ [同步查询] 未找到 {provider} 的 API Key")

                    normalize_provider_key = getattr(
                        importlib.import_module("trader.llm.clients.providers"),
                        "normalize_provider_key",
                    )
                    default_backend_url = getattr(
                        importlib.import_module("trader.llm.clients.providers"),
                        "default_backend_url",
                    )
                    provider_key = normalize_provider_key(provider)

                    # 确定 backend_url
                    backend_url = None
                    if api_base:
                        backend_url = api_base
                        logger.info(
                            f"✅ [同步查询] 模型 {model_name} 使用自定义 API: {api_base}"
                        )
                    elif provider_doc and provider_doc.get("default_base_url"):
                        backend_url = provider_doc["default_base_url"]
                        logger.info(
                            f"✅ [同步查询] 模型 {model_name} 使用厂家默认 API: {backend_url}"
                        )
                    else:
                        backend_url = _get_default_backend_url(provider)
                        logger.warning(
                            f"⚠️ [同步查询] 厂家 {provider} 没有配置 default_base_url，使用硬编码默认值"
                        )

                    if (
                        provider_key == "qwen"
                        and backend_url == "https://dashscope.aliyuncs.com/api/v1"
                    ):
                        backend_url = default_backend_url(provider_key)
                    elif (
                        provider_key == "minimax-token-plan"
                        and "api.minimaxi.com/anthropic"
                        not in str(backend_url).rstrip("/")
                    ):
                        backend_url = (
                            provider_doc.get("default_base_url")
                            if provider_doc and provider_doc.get("default_base_url")
                            else default_backend_url(provider_key)
                        )
                        logger.info(
                            "✅ [同步查询] MiniMax Token Plan 使用 Anthropic 兼容 API: %s",
                            backend_url,
                        )

                    return {
                        "provider": provider_key,
                        "backend_url": backend_url,
                        "api_key": api_key,
                    }

        # 如果数据库中没有找到模型配置，使用默认映射
        logger.warning(f"⚠️ [同步查询] 数据库中未找到模型 {model_name}，使用默认映射")
        provider = _get_default_provider_by_model(model_name)

        # 尝试从厂家配置中获取 default_base_url 和 API Key
        try:
            db = get_postgres_db_sync()
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider})

            backend_url = _get_default_backend_url(provider)
            api_key = None

            if provider_doc:
                if provider_doc.get("default_base_url"):
                    backend_url = provider_doc["default_base_url"]
                    logger.info(
                        f"✅ [同步查询] 使用厂家 {provider} 的 default_base_url: {backend_url}"
                    )

                if provider_doc.get("api_key"):
                    provider_api_key = provider_doc["api_key"]
                    if (
                        provider_api_key
                        and provider_api_key.strip()
                        and provider_api_key != "your-api-key"
                    ):
                        api_key = provider_api_key
                        logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 API Key")

            # 如果厂家配置中没有 API Key，尝试从环境变量获取
            if not api_key:
                api_key = _get_env_api_key_for_provider(provider)
                if api_key:
                    logger.info("✅ [同步查询] 使用环境变量的 API Key")

            normalize_provider_key = getattr(
                importlib.import_module("trader.llm.clients.providers"),
                "normalize_provider_key",
            )
            default_backend_url = getattr(
                importlib.import_module("trader.llm.clients.providers"),
                "default_backend_url",
            )

            provider_key = normalize_provider_key(provider)
            if (
                provider_key == "qwen"
                and backend_url == "https://dashscope.aliyuncs.com/api/v1"
            ):
                backend_url = default_backend_url(provider_key)

            return {
                "provider": provider_key,
                "backend_url": backend_url,
                "api_key": api_key,
            }
        except Exception as e:
            logger.warning(f"⚠️ [同步查询] 无法查询厂家配置: {e}")

        # 最后回退到硬编码的默认 URL 和环境变量 API Key
        normalize_provider_key = getattr(
            importlib.import_module("trader.llm.clients.providers"),
            "normalize_provider_key",
        )

        provider_key = normalize_provider_key(provider)
        return {
            "provider": provider_key,
            "backend_url": _get_default_backend_url(provider_key),
            "api_key": _get_env_api_key_for_provider(provider_key),
        }

    except Exception as e:
        logger.error(f"❌ [同步查询] 查找模型供应商失败: {e}")
        provider = _get_default_provider_by_model(model_name)

        # 尝试从厂家配置中获取 default_base_url 和 API Key
        try:
            db = get_postgres_db_sync()
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider})

            backend_url = _get_default_backend_url(provider)
            api_key = None

            if provider_doc:
                if provider_doc.get("default_base_url"):
                    backend_url = provider_doc["default_base_url"]
                    logger.info(
                        f"✅ [同步查询] 使用厂家 {provider} 的 default_base_url: {backend_url}"
                    )

                if provider_doc.get("api_key"):
                    provider_api_key = provider_doc["api_key"]
                    if (
                        provider_api_key
                        and provider_api_key.strip()
                        and provider_api_key != "your-api-key"
                    ):
                        api_key = provider_api_key
                        logger.info(f"✅ [同步查询] 使用厂家 {provider} 的 API Key")

            # 如果厂家配置中没有 API Key，尝试从环境变量获取
            if not api_key:
                api_key = _get_env_api_key_for_provider(provider)

            return {
                "provider": provider,
                "backend_url": backend_url,
                "api_key": api_key,
            }
        except Exception as e2:
            logger.warning(f"⚠️ [同步查询] 无法查询厂家配置: {e2}")

        # 最后回退到硬编码的默认 URL 和环境变量 API Key
        return {
            "provider": provider,
            "backend_url": _get_default_backend_url(provider),
            "api_key": _get_env_api_key_for_provider(provider),
        }


def _get_env_api_key_for_provider(provider: str) -> Optional[str]:
    """
    从环境变量获取指定供应商的 API Key

    Args:
        provider: 供应商名称，如 'google', 'dashscope' 等

    Returns:
        str: API Key，如果未找到则返回 None
    """
    os = importlib.import_module("os")

    env_key_for_provider = getattr(
        importlib.import_module("trader.llm.clients.providers"), "env_key_for_provider"
    )
    normalize_provider_key = getattr(
        importlib.import_module("trader.llm.clients.providers"),
        "normalize_provider_key",
    )

    provider_key = normalize_provider_key(provider)
    env_key_name = env_key_for_provider(provider_key)
    if not env_key_name and provider_key == "302ai":
        env_key_name = "AI302_API_KEY"
    if not env_key_name and provider_key == "aihubmix":
        env_key_name = "AIHUBMIX_API_KEY"
    if env_key_name:
        api_key = os.getenv(env_key_name)
        if api_key and api_key.strip() and api_key != "your-api-key":
            return api_key

    return None


def _get_default_backend_url(provider: str) -> str:
    """
    根据供应商名称返回默认的 backend_url

    Args:
        provider: 供应商名称，如 'google', 'dashscope' 等

    Returns:
        str: 默认的 backend_url
    """
    default_backend_url = getattr(
        importlib.import_module("trader.llm.clients.providers"), "default_backend_url"
    )
    normalize_provider_key = getattr(
        importlib.import_module("trader.llm.clients.providers"),
        "normalize_provider_key",
    )

    provider_key = normalize_provider_key(provider)
    if provider_key == "302ai":
        url = "https://api.302.ai/v1"
    elif provider_key == "aihubmix":
        url = "https://aihubmix.com/v1"
    else:
        url = default_backend_url(provider_key)

    logger.info(f"🔧 [默认URL] {provider} -> {url}")
    return url


def _get_default_provider_by_model(model_name: str) -> str:
    """
    根据模型名称返回默认的供应商映射
    这是一个后备方案，当数据库查询失败时使用
    """
    # 模型名称到供应商的默认映射
    model_provider_map = {
        # 阿里百炼 (DashScope)
        "qwen-turbo": "qwen",
        "qwen-plus": "qwen",
        "qwen-max": "qwen",
        "qwen-plus-latest": "qwen",
        "qwen-max-longcontext": "qwen",
        # OpenAI
        "gpt-3.5-turbo": "openai",
        "gpt-4": "openai",
        "gpt-4-turbo": "openai",
        "gpt-4o": "openai",
        "gpt-4o-mini": "openai",
        # Google
        "gemini-pro": "google",
        "gemini-2.0-flash": "google",
        "gemini-2.0-flash-thinking-exp": "google",
        # DeepSeek
        "deepseek-chat": "deepseek",
        "deepseek-coder": "deepseek",
        # 智谱AI
        "glm-4": "glm",
        "glm-3-turbo": "glm",
        "chatglm3-6b": "glm",
    }

    provider = model_provider_map.get(model_name, "qwen")  # 默认使用阿里百炼
    logger.info(f"🔧 使用默认映射: {model_name} -> {provider}")
    return provider


def create_analysis_config(
    research_depth,  # 支持数字(1-5)或字符串("快速", "标准", "深度")
    selected_analysts: list,
    quick_model: str,
    deep_model: str,
    llm_provider: str,
    market_type: str = "A股",
    quick_model_config: Optional[dict] = None,  # 新增：快速模型的完整配置
    deep_model_config: Optional[dict] = None,  # 新增：深度模型的完整配置
) -> dict:
    """
    创建分析配置 - 支持数字等级和中文等级

    Args:
        research_depth: 研究深度，支持数字(1-5)或中文("快速", "基础", "标准", "深度", "全面")
        selected_analysts: 选中的分析师列表
        quick_model: 快速分析模型
        deep_model: 深度分析模型
        llm_provider: LLM供应商
        market_type: 市场类型
        quick_model_config: 快速模型的完整配置（包含 max_tokens、temperature、timeout 等）
        deep_model_config: 深度模型的完整配置（包含 max_tokens、temperature、timeout 等）

    Returns:
        dict: 完整的分析配置
    """
    # 🔍 [调试] 记录接收到的原始参数
    logger.info(
        f"🔍 [配置创建] 接收到的research_depth参数: {research_depth} (类型: {type(research_depth).__name__})"
    )

    # 数字等级到中文等级的映射
    numeric_to_chinese = {1: "快速", 2: "基础", 3: "标准", 4: "深度", 5: "全面"}

    # 标准化研究深度：支持数字输入
    if isinstance(research_depth, (int, float)):
        research_depth = int(research_depth)
        if research_depth in numeric_to_chinese:
            chinese_depth = numeric_to_chinese[research_depth]
            logger.info(
                f"🔢 [等级转换] 数字等级 {research_depth} → 中文等级 '{chinese_depth}'"
            )
            research_depth = chinese_depth
        else:
            logger.warning(f"⚠️ 无效的数字等级: {research_depth}，使用默认标准分析")
            research_depth = "标准"
    elif isinstance(research_depth, str):
        # 如果是字符串形式的数字，转换为整数
        if research_depth.isdigit():
            numeric_level = int(research_depth)
            if numeric_level in numeric_to_chinese:
                chinese_depth = numeric_to_chinese[numeric_level]
                logger.info(
                    f"🔢 [等级转换] 字符串数字 '{research_depth}' → 中文等级 '{chinese_depth}'"
                )
                research_depth = chinese_depth
            else:
                logger.warning(
                    f"⚠️ 无效的字符串数字等级: {research_depth}，使用默认标准分析"
                )
                research_depth = "标准"
        # 如果已经是中文等级，直接使用
        elif research_depth in ["快速", "基础", "标准", "深度", "全面"]:
            logger.info(f"📝 [等级确认] 使用中文等级: '{research_depth}'")
        else:
            logger.warning(f"⚠️ 未知的研究深度: {research_depth}，使用默认标准分析")
            research_depth = "标准"
    else:
        logger.warning(
            f"⚠️ 无效的研究深度类型: {type(research_depth)}，使用默认标准分析"
        )
        research_depth = "标准"

    DEFAULT_CONFIG = getattr(
        importlib.import_module("trader.default"), "DEFAULT_CONFIG"
    )

    # 从DEFAULT_CONFIG开始，完全复制web目录的逻辑
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = llm_provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    config["checkpoint_enabled"] = True

    # 根据研究深度调整配置 - 支持5个级别（与Web界面保持一致）
    if research_depth == "快速":
        # 1级 - 快速分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = False  # 禁用记忆以加速
        config["online_tools"] = False  # 禁用在线工具以加速
        logger.info(f"🔧 [1级-快速分析] {market_type}禁用在线工具，优先保证速度")
        logger.info(
            f"🔧 [1级-快速分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}"
        )

    elif research_depth == "基础":
        # 2级 - 基础分析
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 1
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [2级-基础分析] {market_type}使用在线工具，获取最新数据")
        logger.info(
            f"🔧 [2级-基础分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}"
        )

    elif research_depth == "标准":
        # 3级 - 标准分析（推荐）
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [3级-标准分析] {market_type}平衡速度和质量（推荐）")
        logger.info(
            f"🔧 [3级-标准分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}"
        )

    elif research_depth == "深度":
        # 4级 - 深度分析
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [4级-深度分析] {market_type}多轮辩论，深度研究")
        logger.info(
            f"🔧 [4级-深度分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}"
        )

    elif research_depth == "全面":
        # 5级 - 全面分析
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["memory_enabled"] = True
        config["online_tools"] = True
        logger.info(f"🔧 [5级-全面分析] {market_type}最全面的分析，最高质量")
        logger.info(
            f"🔧 [5级-全面分析] 使用用户配置的模型: quick={quick_model}, deep={deep_model}"
        )

    else:
        # 默认使用标准分析
        logger.warning(f"⚠️ 未知的研究深度: {research_depth}，使用标准分析")
        config["max_debate_rounds"] = 1
        config["max_risk_discuss_rounds"] = 2
        config["memory_enabled"] = True
        config["online_tools"] = True

    # 🔧 获取 backend_url 和 API Key（优先级：模型配置 > 厂家配置 > 环境变量）
    try:
        # 1️⃣ 优先从数据库获取（包含模型配置的 api_base、API Key 和厂家的 default_base_url、API Key）
        quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
        deep_provider_info = get_provider_and_url_by_model_sync(deep_model)

        config["backend_url"] = quick_provider_info["backend_url"]
        config["quick_api_key"] = quick_provider_info.get(
            "api_key"
        )  # 🔥 保存快速模型的 API Key
        config["deep_api_key"] = deep_provider_info.get(
            "api_key"
        )  # 🔥 保存深度模型的 API Key

        logger.info(
            f"✅ 使用数据库配置的 backend_url: {quick_provider_info['backend_url']}"
        )
        logger.info(
            f"   来源: 模型 {quick_model} 的配置或厂家 {quick_provider_info['provider']} 的默认地址"
        )
        logger.info(
            f"🔑 快速模型 API Key: {'已配置' if config['quick_api_key'] else '未配置（将使用环境变量）'}"
        )
        logger.info(
            f"🔑 深度模型 API Key: {'已配置' if config['deep_api_key'] else '未配置（将使用环境变量）'}"
        )
    except Exception as e:
        logger.warning(f"⚠️  无法从数据库获取 backend_url 和 API Key: {e}")
        config["backend_url"] = _get_default_backend_url(llm_provider)

        logger.info(f"⚠️  使用回退的 backend_url: {config['backend_url']}")

    # 添加分析师配置
    config["selected_analysts"] = selected_analysts
    config["debug"] = False

    # 🔧 添加research_depth到配置中，使工具函数能够访问分析级别信息
    config["research_depth"] = research_depth

    # 🔧 添加模型配置参数（max_tokens、temperature、timeout、retry_times）
    if quick_model_config:
        config["quick_model_config"] = quick_model_config
        logger.info(
            f"🔧 [快速模型配置] max_tokens={quick_model_config.get('max_tokens')}, "
            f"temperature={quick_model_config.get('temperature')}, "
            f"timeout={quick_model_config.get('timeout')}, "
            f"retry_times={quick_model_config.get('retry_times')}"
        )

    if deep_model_config:
        config["deep_model_config"] = deep_model_config
        logger.info(
            f"🔧 [深度模型配置] max_tokens={deep_model_config.get('max_tokens')}, "
            f"temperature={deep_model_config.get('temperature')}, "
            f"timeout={deep_model_config.get('timeout')}, "
            f"retry_times={deep_model_config.get('retry_times')}"
        )

    logger.info("📋 ========== 创建分析配置完成 ==========")
    logger.info(f"   🎯 研究深度: {research_depth}")
    logger.info(f"   🔥 辩论轮次: {config['max_debate_rounds']}")
    logger.info(f"   ⚖️ 风险讨论轮次: {config['max_risk_discuss_rounds']}")
    logger.info(f"   💾 记忆功能: {config['memory_enabled']}")
    logger.info(f"   🌐 在线工具: {config['online_tools']}")
    logger.info(f"   🤖 LLM供应商: {llm_provider}")
    logger.info(f"   ⚡ 快速模型: {config['quick_think_llm']}")
    logger.info(f"   🧠 深度模型: {config['deep_think_llm']}")
    logger.info("📋 ========================================")

    return config
