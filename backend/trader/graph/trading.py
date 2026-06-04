import importlib
import json

# TradingAgents/graph/trading_graph.py
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

from trader.agents import Toolkit
from trader.agents.utils.log import TradingMemoryLog
from trader.agents.utils.memory import FinancialSituationMemory
from trader.agents.utils.utils import (
    build_instrument_context,
    resolve_instrument_identity,
)
from trader.default import DEFAULT_CONFIG
from trader.flows.config import set_config as set_dataflows_config
from trader.flows.interface import set_config as set_interface_config
from trader.flows.utils import safe_ticker_component
from trader.llm.clients import create_llm_client
from trader.llm.clients.providers import env_key_for_provider, normalize_provider_key
from trader.utils.logging.manager import get_logger

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditions import ConditionalLogic
from .propagation import Propagator
from .reflection import Reflector
from .setup import GraphSetup
from .signals import SignalProcessor

logger = get_logger("agents")


def _configured_provider_kwargs(
    config: Dict[str, Any], provider: Optional[str]
) -> Dict[str, Any]:
    """Return provider-specific runtime knobs from graph config.

    Keep these provider-scoped. Some OpenAI-compatible endpoints reject
    reasoning-specific fields, and Anthropic effort support is model-gated by
    the Anthropic client.
    """
    normalized_provider = normalize_provider_key(provider) if provider else None
    provider_kwargs: Dict[str, Any] = {}

    if normalized_provider == "google" and config.get("google_thinking_level"):
        provider_kwargs["thinking_level"] = config["google_thinking_level"]
    if normalized_provider in {"openai", "custom_openai"} and config.get(
        "openai_reasoning_effort"
    ):
        provider_kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    if normalized_provider in {"anthropic", "minimax-token-plan"} and config.get(
        "anthropic_effort"
    ):
        provider_kwargs["effort"] = config["anthropic_effort"]

    return provider_kwargs


def create_llm_by_provider(
    provider: str,
    model: str,
    backend_url: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    api_key: Optional[str] = None,
    **extra_kwargs: Any,
):
    """
    根据 provider 创建对应的 LLM 实例

    Args:
        provider: 供应商名称 (google, dashscope, deepseek, openai, etc.)
        model: 模型名称
        backend_url: API 地址
        temperature: 温度参数
        max_tokens: 最大 token 数
        timeout: 超时时间
        api_key: API Key（可选，如果未提供则从环境变量读取）

    Returns:
        LLM 实例
    """
    logger.info(f"🔧 [创建LLM] provider={provider}, model={model}, url={backend_url}")
    logger.info(f"🔑 [API Key] 来源: {'数据库配置' if api_key else '环境变量'}")

    normalized_provider = normalize_provider_key(provider)

    if normalized_provider in {
        "openai",
        "siliconflow",
        "openrouter",
        "aihubmix",
        "ollama",
        "deepseek",
        "qwen",
        "qwen-cn",
        "glm",
        "glm-cn",
        "xai",
        "minimax",
        "minimax-cn",
        "custom_openai",
        "qianfan",
    }:
        if not api_key:
            if normalized_provider == "siliconflow":
                api_key = os.getenv("SILICONFLOW_API_KEY") or ""
            elif normalized_provider == "openrouter":
                api_key = (
                    os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
                )
            elif normalized_provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY") or ""
            else:
                env_key = env_key_for_provider(normalized_provider)
                if env_key:
                    api_key = os.getenv(env_key) or ""

        factory_provider = (
            "openai" if normalized_provider == "siliconflow" else normalized_provider
        )
        client = create_llm_client(
            provider=factory_provider,
            model=model,
            base_url=backend_url,
            api_key=api_key,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            timeout=timeout,
            **extra_kwargs,
        )
        return client.get_llm()

    if normalized_provider == "google":
        # 优先使用传入的 API Key，否则从环境变量读取
        google_api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError(
                "使用Google需要设置GOOGLE_API_KEY环境变量或在数据库中配置API Key"
            )

        client = create_llm_client(
            provider="google",
            model=model,
            base_url=backend_url if backend_url else None,
            api_key=google_api_key,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            timeout=timeout,
            **extra_kwargs,
        )
        return client.get_llm()

    elif normalized_provider in {"anthropic", "minimax-token-plan"}:
        if not api_key:
            env_key = env_key_for_provider(normalized_provider)
            api_key = os.getenv(env_key) or os.getenv("ANTHROPIC_API_KEY") or ""

        client = create_llm_client(
            provider=normalized_provider,
            model=model,
            base_url=backend_url,
            api_key=api_key,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            timeout=timeout,
            **extra_kwargs,
        )
        return client.get_llm()

    else:
        # 🔧 自定义厂家：使用 OpenAI 兼容模式
        logger.info(f"🔧 使用 OpenAI 兼容模式处理自定义厂家: {provider}")

        # 尝试从环境变量获取 API Key（支持多种命名格式）
        api_key_candidates = [
            f"{provider.upper()}_API_KEY",  # 例如: KYX_API_KEY
            f"{provider}_API_KEY",  # 例如: kyx_API_KEY
            "CUSTOM_OPENAI_API_KEY",  # 通用环境变量
        ]

        custom_api_key = None
        for env_var in api_key_candidates:
            custom_api_key = os.getenv(env_var)
            if custom_api_key:
                logger.info(f"✅ 从环境变量 {env_var} 获取到 API Key")
                break

        if not custom_api_key:
            logger.warning(
                f"⚠️ 未找到自定义厂家 {provider} 的 API Key，尝试使用默认配置"
            )

        params: Dict[str, Any] = {
            "model": model,
            "base_url": backend_url,
            "api_key": custom_api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        return cast(Any, ChatOpenAI)(**params)


def _create_provider_pair(
    provider: str,
    config: Dict[str, Any],
    quick_temperature: float,
    quick_max_tokens: int,
    quick_timeout: int,
    deep_temperature: float,
    deep_max_tokens: int,
    deep_timeout: int,
    backend_url: Optional[str] = None,
    api_key: Optional[str] = None,
    quick_extra_kwargs: Optional[Dict[str, Any]] = None,
    deep_extra_kwargs: Optional[Dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    resolved_backend_url = (
        backend_url if backend_url is not None else config.get("backend_url", "")
    )
    shared_api_key = (
        api_key or config.get("quick_api_key") or config.get("deep_api_key")
    )
    configured_kwargs = _configured_provider_kwargs(config, provider)
    quick_extra_kwargs = {**configured_kwargs, **(quick_extra_kwargs or {})}
    deep_extra_kwargs = {**configured_kwargs, **(deep_extra_kwargs or {})}

    deep_llm = create_llm_by_provider(
        provider=provider,
        model=config["deep_think_llm"],
        backend_url=resolved_backend_url,
        temperature=deep_temperature,
        max_tokens=deep_max_tokens,
        timeout=deep_timeout,
        api_key=shared_api_key,
        **deep_extra_kwargs,
    )
    quick_llm = create_llm_by_provider(
        provider=provider,
        model=config["quick_think_llm"],
        backend_url=resolved_backend_url,
        temperature=quick_temperature,
        max_tokens=quick_max_tokens,
        timeout=quick_timeout,
        api_key=shared_api_key,
        **quick_extra_kwargs,
    )
    return deep_llm, quick_llm


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        provider_kwargs: Dict[str, Any] = {}
        temperature = self.config.get("temperature")
        if temperature not in (None, ""):
            provider_kwargs["temperature"] = float(temperature)
        if self.config.get("google_thinking_level"):
            provider_kwargs["thinking_level"] = self.config["google_thinking_level"]
        if self.config.get("openai_reasoning_effort"):
            provider_kwargs["reasoning_effort"] = self.config["openai_reasoning_effort"]
        if self.config.get("anthropic_effort"):
            provider_kwargs["effort"] = self.config["anthropic_effort"]
        return provider_kwargs

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Keep both CN runtime settings and migrated upstream dataflow routing in sync.
        set_interface_config(self.config)
        set_dataflows_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs
        # 🔧 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
        quick_config = self.config.get("quick_model_config", {})
        deep_config = self.config.get("deep_model_config", {})

        configured_temperature = self.config.get("temperature")
        default_temperature = (
            0.7
            if configured_temperature in (None, "")
            else float(configured_temperature)
        )

        # 读取快速模型参数
        quick_max_tokens = quick_config.get("max_tokens", 4000)
        quick_temperature = quick_config.get("temperature", default_temperature)
        quick_timeout = quick_config.get("timeout", 180)

        # 读取深度模型参数
        deep_max_tokens = deep_config.get("max_tokens", 4000)
        deep_temperature = deep_config.get("temperature", default_temperature)
        deep_timeout = deep_config.get("timeout", 180)

        # 🔧 检查是否为混合模式（快速模型和深度模型来自不同厂家）
        quick_provider = self.config.get("quick_provider")
        deep_provider = self.config.get("deep_provider")
        normalized_quick_provider = (
            normalize_provider_key(quick_provider) if quick_provider else None
        )
        normalized_deep_provider = (
            normalize_provider_key(deep_provider) if deep_provider else None
        )
        quick_backend_url = self.config.get("quick_backend_url")
        deep_backend_url = self.config.get("deep_backend_url")
        normalized_provider = normalize_provider_key(self.config["llm_provider"])

        if (
            normalized_quick_provider
            and normalized_deep_provider
            and normalized_quick_provider != normalized_deep_provider
        ):
            # 混合模式：快速模型和深度模型来自不同厂家
            logger.info("🔀 [混合模式] 检测到不同厂家的模型组合")
            logger.info(
                f"   快速模型: {self.config['quick_think_llm']} ({normalized_quick_provider})"
            )
            logger.info(
                f"   深度模型: {self.config['deep_think_llm']} ({normalized_deep_provider})"
            )

            # 使用统一的函数创建 LLM 实例
            self.quick_thinking_llm = create_llm_by_provider(
                provider=normalized_quick_provider,
                model=self.config["quick_think_llm"],
                backend_url=quick_backend_url or self.config.get("backend_url", ""),
                temperature=quick_temperature,
                max_tokens=quick_max_tokens,
                timeout=quick_timeout,
                api_key=self.config.get("quick_api_key"),  # 🔥 传递 API Key
                **_configured_provider_kwargs(self.config, normalized_quick_provider),
            )

            self.deep_thinking_llm = create_llm_by_provider(
                provider=normalized_deep_provider,
                model=self.config["deep_think_llm"],
                backend_url=deep_backend_url or self.config.get("backend_url", ""),
                temperature=deep_temperature,
                max_tokens=deep_max_tokens,
                timeout=deep_timeout,
                api_key=self.config.get("deep_api_key"),  # 🔥 传递 API Key
                **_configured_provider_kwargs(self.config, normalized_deep_provider),
            )

            logger.info("✅ [混合模式] LLM 实例创建成功")

        elif normalized_provider in {
            "openai",
            "siliconflow",
            "openrouter",
            "aihubmix",
            "ollama",
        }:
            provider = normalized_provider
            logger.info(
                f"🔧 [{provider}-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [{provider}-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            api_key = None
            if provider == "siliconflow":
                api_key = os.getenv("SILICONFLOW_API_KEY")
                if not api_key:
                    raise ValueError(
                        "使用SiliconFlow需要设置SILICONFLOW_API_KEY环境变量"
                    )
            elif provider == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "使用OpenRouter需要设置OPENROUTER_API_KEY或OPENAI_API_KEY环境变量"
                    )
            elif provider == "aihubmix":
                api_key = os.getenv("AIHUBMIX_API_KEY")
                if not api_key:
                    raise ValueError("使用AiHubMix需要设置AIHUBMIX_API_KEY环境变量")

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider=provider,
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config["backend_url"],
                api_key=api_key,
            )
        elif normalized_provider in {"anthropic", "minimax-token-plan"}:
            logger.info(
                f"🔧 [Anthropic-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [Anthropic-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            anthropic_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv(env_key_for_provider(normalized_provider))
                or os.getenv("ANTHROPIC_API_KEY")
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider=normalized_provider,
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config.get("backend_url"),
                api_key=anthropic_api_key,
            )
        elif normalized_provider == "google":
            # 使用统一 llm_clients 入口，但底层仍返回 ChatGoogleOpenAI 兼容适配器
            logger.info(
                "🔧 使用统一 llm_clients 路径初始化 Google AI（保留工具调用兼容行为）"
            )

            # 🔥 优先使用数据库配置的 API Key，否则从环境变量读取
            google_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("GOOGLE_API_KEY")
            )
            if not google_api_key:
                raise ValueError(
                    "使用Google AI需要在数据库中配置API Key或设置GOOGLE_API_KEY环境变量"
                )

            logger.info(
                f"🔑 [Google AI] API Key 来源: {'数据库配置' if self.config.get('quick_api_key') or self.config.get('deep_api_key') else '环境变量'}"
            )

            logger.info(
                f"🔧 [Google-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [Google-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            # 获取 backend_url（如果配置中有的话）
            backend_url = self.config.get("backend_url")
            if backend_url:
                logger.info(f"🔧 [Google AI] 使用配置的 backend_url: {backend_url}")
            else:
                logger.info("🔧 [Google AI] 未配置 backend_url，使用默认端点")

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="google",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url if backend_url else None,
                api_key=google_api_key,
                quick_extra_kwargs={"transport": "rest"},
            )

            logger.info(
                "✅ [Google AI] 已启用优化的工具调用和内容格式处理并应用用户配置的模型参数"
            )
        elif normalized_provider == "qwen":
            logger.info("🔧 使用统一 llm_clients 路径初始化阿里百炼/通义千问")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="qwen",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=self.config.get("backend_url"),
            )
            logger.info(
                "✅ [阿里百炼] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "deepseek":
            deepseek_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("DEEPSEEK_API_KEY")
            )
            if not deepseek_api_key:
                raise ValueError("使用DeepSeek需要设置DEEPSEEK_API_KEY环境变量")

            deepseek_base_url = self.config.get("backend_url") or os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="deepseek",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=deepseek_base_url,
                api_key=deepseek_api_key,
            )
            logger.info(
                "✅ [DeepSeek] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "custom_openai":
            custom_api_key = os.getenv("CUSTOM_OPENAI_API_KEY")
            if not custom_api_key:
                raise ValueError(
                    "使用自定义OpenAI端点需要设置CUSTOM_OPENAI_API_KEY环境变量"
                )

            custom_base_url = self.config.get(
                "custom_openai_base_url", "https://api.openai.com/v1"
            )
            logger.info(f"🔧 [自定义OpenAI] 使用端点: {custom_base_url}")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="custom_openai",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=custom_base_url,
                api_key=custom_api_key,
            )
            logger.info(
                "✅ [自定义OpenAI] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        elif normalized_provider == "qianfan":
            # 百度千帆（文心一言）配置 - 统一由适配器内部读取与校验 QIANFAN_API_KEY
            logger.info(
                f"🔧 [千帆-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [千帆-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="qianfan",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
            )
            logger.info("✅ [千帆] 文心一言适配器已配置成功并应用用户配置的模型参数")
        elif normalized_provider == "glm":
            # 🔥 优先使用数据库配置的 API Key，否则从环境变量读取
            zhipu_api_key = (
                self.config.get("quick_api_key")
                or self.config.get("deep_api_key")
                or os.getenv("ZHIPU_API_KEY")
            )
            logger.info(
                f"🔑 [智谱AI] API Key 来源: {'数据库配置' if self.config.get('quick_api_key') or self.config.get('deep_api_key') else '环境变量'}"
            )

            if not zhipu_api_key:
                raise ValueError(
                    "使用智谱AI需要在数据库中配置API Key或设置ZHIPU_API_KEY环境变量"
                )

            # 🔧 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
            quick_config = self.config.get("quick_model_config", {})
            deep_config = self.config.get("deep_model_config", {})

            quick_max_tokens = quick_config.get("max_tokens", 4000)
            quick_temperature = quick_config.get("temperature", default_temperature)
            quick_timeout = quick_config.get("timeout", 180)

            deep_max_tokens = deep_config.get("max_tokens", 4000)
            deep_temperature = deep_config.get("temperature", default_temperature)
            deep_timeout = deep_config.get("timeout", 180)

            logger.info(
                f"🔧 [智谱AI-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [智谱AI-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            # 获取 backend_url（如果配置中有的话）
            backend_url = self.config.get("backend_url")
            if backend_url:
                logger.info(f"🔧 [智谱AI] 使用配置的 backend_url: {backend_url}")
            else:
                logger.info("🔧 [智谱AI] 未配置 backend_url，使用默认端点")
            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="glm",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url,
                api_key=zhipu_api_key,
            )

            logger.info(
                "✅ [智谱AI] 已通过 llm_clients 初始化成功并应用用户配置的模型参数"
            )
        else:
            provider_name = self.config["llm_provider"]
            logger.info(f"🔧 使用统一 llm_clients 路径处理自定义厂家: {provider_name}")
            api_key_candidates = [
                f"{provider_name.upper()}_API_KEY",  # 例如: KYX_API_KEY
                f"{provider_name}_API_KEY",  # 例如: kyx_API_KEY
                "CUSTOM_OPENAI_API_KEY",  # 通用环境变量
            ]

            custom_api_key = None
            for env_var in api_key_candidates:
                custom_api_key = os.getenv(env_var)
                if custom_api_key:
                    logger.info(f"✅ 从环境变量 {env_var} 获取到 API Key")
                    break

            if not custom_api_key:
                raise ValueError(
                    f"使用自定义厂家 {provider_name} 需要设置以下环境变量之一:\n"
                    f"  - {provider_name.upper()}_API_KEY\n"
                    f"  - CUSTOM_OPENAI_API_KEY"
                )

            # 获取 backend_url（从配置中获取）
            backend_url = self.config.get("backend_url")
            if not backend_url:
                raise ValueError(
                    f"使用自定义厂家 {provider_name} 需要在数据库配置中设置 default_base_url"
                )

            logger.info(f"🔧 [自定义厂家 {provider_name}] 使用端点: {backend_url}")

            # 🔧 从配置中读取模型参数
            quick_config = self.config.get("quick_model_config", {})
            deep_config = self.config.get("deep_model_config", {})

            quick_max_tokens = quick_config.get("max_tokens", 4000)
            quick_temperature = quick_config.get("temperature", default_temperature)
            quick_timeout = quick_config.get("timeout", 180)

            deep_max_tokens = deep_config.get("max_tokens", 4000)
            deep_temperature = deep_config.get("temperature", default_temperature)
            deep_timeout = deep_config.get("timeout", 180)

            logger.info(
                f"🔧 [{provider_name}-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s"
            )
            logger.info(
                f"🔧 [{provider_name}-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s"
            )

            self.deep_thinking_llm, self.quick_thinking_llm = _create_provider_pair(
                provider="custom_openai",
                config=self.config,
                quick_temperature=quick_temperature,
                quick_max_tokens=quick_max_tokens,
                quick_timeout=quick_timeout,
                deep_temperature=deep_temperature,
                deep_max_tokens=deep_max_tokens,
                deep_timeout=deep_timeout,
                backend_url=backend_url,
                api_key=custom_api_key,
            )

            logger.info(
                f"✅ [自定义厂家 {provider_name}] 已配置自定义端点并应用用户配置的模型参数"
            )

        self.toolkit = Toolkit(config=self.config)

        # Preserve existing CN role memories; TradingMemoryLog is additive.
        memory_enabled = self.config.get("memory_enabled", True)
        if memory_enabled:
            self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
            self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
            self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
            self.invest_judge_memory = FinancialSituationMemory(
                "invest_judge_memory", self.config
            )
            self.risk_manager_memory = FinancialSituationMemory(
                "risk_manager_memory", self.config
            )
        else:
            self.bull_memory = None
            self.bear_memory = None
            self.trader_memory = None
            self.invest_judge_memory = None
            self.risk_manager_memory = None

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        # 🔥 [修复] 从配置中读取辩论轮次参数
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config.get("max_debate_rounds", 1),
            max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1),
        )
        logger.info("🔧 [ConditionalLogic] 初始化完成:")
        logger.info(
            f"   - max_debate_rounds: {self.conditional_logic.max_debate_rounds}"
        )
        logger.info(
            f"   - max_risk_discuss_rounds: {self.conditional_logic.max_risk_discuss_rounds}"
        )

        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.toolkit,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
            self.config,
            getattr(self, "react_llm", None),
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)
        self.memory_log = TradingMemoryLog(self.config)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.workflow = self.graph_setup.setup_graph(selected_analysts)
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources.

        注意：ToolNode 包含所有可能的工具，但 LLM 只会调用它绑定的工具。
        ToolNode 的作用是执行 LLM 生成的 tool_calls，而不是限制 LLM 可以调用哪些工具。
        """
        return {
            "market": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_market_data_unified,
                    # 在线工具（备用）
                    self.toolkit.get_yfin_data_online,
                    self.toolkit.get_stockstats_indicators_report_online,
                    # 离线工具（备用）
                    self.toolkit.get_yfin_data,
                    self.toolkit.get_stockstats_indicators_report,
                ]
            ),
            "social": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_sentiment_unified,
                    # 在线工具（备用）
                    self.toolkit.get_stock_news_openai,
                    # 离线工具（备用）
                    self.toolkit.get_reddit_stock_info,
                ]
            ),
            "news": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_news_unified,
                    # 在线工具（备用）
                    self.toolkit.get_global_news_openai,
                    self.toolkit.get_google_news,
                    # 离线工具（备用）
                    self.toolkit.get_finnhub_news,
                    self.toolkit.get_reddit_news,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # 统一工具（推荐）
                    self.toolkit.get_stock_fundamentals_unified,
                    # 离线工具（备用）
                    self.toolkit.get_finnhub_company_insider_sentiment,
                    self.toolkit.get_finnhub_company_insider_transactions,
                    self.toolkit.get_simfin_balance_sheet,
                    self.toolkit.get_simfin_cashflow,
                    self.toolkit.get_simfin_income_stmt,
                    # 中国市场工具（备用）
                    self.toolkit.get_china_stock_data,
                    self.toolkit.get_china_fundamentals,
                ]
            ),
        }

    def resolve_instrument_context(self, ticker: str, asset_type: str = "stock") -> str:
        identity = resolve_instrument_identity(ticker)
        return build_instrument_context(ticker, asset_type, identity)

    def _resolve_benchmark(self, ticker: str) -> str:
        explicit = self.config.get("benchmark_ticker")
        if explicit:
            return explicit
        benchmark_map = self.config.get("benchmark_map", {})
        ticker_upper = str(ticker).upper()
        for suffix, benchmark in benchmark_map.items():
            if suffix and ticker_upper.endswith(str(suffix).upper()):
                return benchmark
        return benchmark_map.get("", "SPY")

    def _fetch_returns(
        self,
        ticker: str,
        trade_date: str,
        holding_days: int = 5,
        benchmark: str = "SPY",
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        try:
            yf = importlib.import_module("yfinance")

            start = datetime.strptime(str(trade_date), "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)
            end_str = end.strftime("%Y-%m-%d")
            stock = yf.Ticker(ticker).history(start=str(trade_date), end=end_str)
            bench = yf.Ticker(benchmark).history(start=str(trade_date), end=end_str)
            if len(stock) < 2 or len(bench) < 2:
                return None, None, None
            actual_days = min(holding_days, len(stock) - 1, len(bench) - 1)
            raw = float(
                (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
                / stock["Close"].iloc[0]
            )
            bench_ret = float(
                (bench["Close"].iloc[actual_days] - bench["Close"].iloc[0])
                / bench["Close"].iloc[0]
            )
            return raw, raw - bench_ret, actual_days
        except Exception as exc:
            logger.warning(
                "Could not resolve outcome for %s on %s vs %s: %s",
                ticker,
                trade_date,
                benchmark,
                exc,
            )
            return None, None, None

    def _resolve_pending_entries(self, ticker: str) -> None:
        pending = [
            e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker
        ]
        if not pending:
            return
        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker, entry["date"], benchmark=benchmark
            )
            if raw is None or alpha is None:
                continue
            reflection = self.reflector.reflect_on_final_decision(
                final_decision=entry.get("decision", ""),
                raw_return=raw,
                alpha_return=alpha,
                benchmark_name=benchmark,
            )
            updates.append(
                {
                    "ticker": ticker,
                    "trade_date": entry["date"],
                    "raw_return": raw,
                    "alpha_return": alpha,
                    "holding_days": days,
                    "reflection": reflection,
                }
            )
        if updates:
            self.memory_log.batch_update_with_outcomes(updates)

    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        self._resolve_pending_entries(company_name)
        past_context = self.memory_log.get_past_context(company_name)
        instrument_context = self.resolve_instrument_context(company_name, asset_type)
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        args = self.propagator.get_graph_args()
        if self.config.get("checkpoint_enabled"):
            args.setdefault("config", {}).setdefault("configurable", {})[
                "thread_id"
            ] = thread_id(company_name, str(trade_date))
        final_state = cast(Any, self.graph).invoke(init_agent_state, **args)
        self.curr_state = final_state
        self._log_state(trade_date, final_state)
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=str(trade_date),
            final_trade_decision=final_state["final_trade_decision"],
        )
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
        return final_state, self.process_signal(
            final_state["final_trade_decision"], company_name
        )

    def propagate(
        self,
        company_name,
        trade_date,
        progress_callback=None,
        task_id=None,
        asset_type: str = "stock",
    ):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name: Company name or stock symbol
            trade_date: Date for analysis
            progress_callback: Optional callback function for progress updates
            task_id: Optional task ID for tracking performance data
        """

        # 添加详细的接收日志
        logger.debug(
            "🔍 [GRAPH DEBUG] ===== TradingAgentsGraph.propagate 接收参数 ====="
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 接收到的company_name: '{company_name}' (类型: {type(company_name)})"
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 接收到的trade_date: '{trade_date}' (类型: {type(trade_date)})"
        )
        logger.debug(f"🔍 [GRAPH DEBUG] 接收到的task_id: '{task_id}'")

        if not isinstance(self, TradingAgentsGraph) and callable(
            getattr(self, "_run_graph", None)
        ):
            return self._run_graph(company_name, trade_date, asset_type=asset_type)

        self.ticker = company_name
        logger.debug(f"🔍 [GRAPH DEBUG] 设置self.ticker: '{self.ticker}'")

        self._resolve_pending_entries(company_name)
        past_context = self.memory_log.get_past_context(company_name)
        instrument_context = self.resolve_instrument_context(company_name, asset_type)

        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)
            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )
            if step is not None:
                logger.info(
                    f"🔄 [Checkpoint] 从步骤 {step} 恢复: {company_name} {trade_date}"
                )
            else:
                logger.info(
                    f"🆕 [Checkpoint] 开始新的分析: {company_name} {trade_date}"
                )

        # Initialize state
        logger.debug(
            f"🔍 [GRAPH DEBUG] 创建初始状态，传递参数: company_name='{company_name}', trade_date='{trade_date}'"
        )
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 初始状态中的company_of_interest: '{init_agent_state.get('company_of_interest', 'NOT_FOUND')}'"
        )
        logger.debug(
            f"🔍 [GRAPH DEBUG] 初始状态中的trade_date: '{init_agent_state.get('trade_date', 'NOT_FOUND')}'"
        )

        # 初始化计时器
        node_timings = {}  # 记录每个节点的执行时间
        total_start_time = time.time()  # 总体开始时间
        current_node_start = None  # 当前节点开始时间
        current_node_name = None  # 当前节点名称

        # 保存task_id用于后续保存性能数据
        self._current_task_id = task_id

        # 根据是否有进度回调选择不同的stream_mode
        args = self.propagator.get_graph_args(
            use_progress_callback=bool(progress_callback)
        )
        if self.config.get("checkpoint_enabled"):
            args.setdefault("config", {}).setdefault("configurable", {})[
                "thread_id"
            ] = thread_id(company_name, str(trade_date))

        try:
            if self.debug:
                trace = []
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    for node_name in chunk.keys():
                        if not node_name.startswith("__"):
                            if current_node_name and current_node_start:
                                elapsed = time.time() - current_node_start
                                node_timings[current_node_name] = elapsed
                                logger.info(
                                    f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒"
                                )

                            current_node_name = node_name
                            current_node_start = time.time()
                            break

                    if progress_callback and args.get("stream_mode") == "updates":
                        self._send_progress_update(chunk, progress_callback)
                        if final_state is None:
                            final_state = init_agent_state.copy()
                        for node_name, node_update in chunk.items():
                            if not node_name.startswith("__"):
                                final_state.update(node_update)
                    else:
                        if len(chunk.get("messages", [])) > 0:
                            chunk["messages"][-1].pretty_print()
                        trace.append(chunk)
                        final_state = chunk

                if trace:
                    final_state = trace[-1]
            elif progress_callback:
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    for node_name in chunk.keys():
                        if not node_name.startswith("__"):
                            if current_node_name and current_node_start:
                                elapsed = time.time() - current_node_start
                                node_timings[current_node_name] = elapsed
                                logger.info(
                                    f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒"
                                )
                                logger.info(
                                    f"🔍 [TIMING] 节点切换: {current_node_name} → {node_name}"
                                )

                            current_node_name = node_name
                            current_node_start = time.time()
                            logger.info(f"🔍 [TIMING] 开始计时: {node_name}")
                            break

                    self._send_progress_update(chunk, progress_callback)
                    if final_state is None:
                        final_state = init_agent_state.copy()
                    for node_name, node_update in chunk.items():
                        if not node_name.startswith("__"):
                            final_state.update(node_update)
            else:
                logger.info("⏱️ 使用 invoke 模式执行分析（无进度回调）")
                final_state = None
                for chunk in cast(Any, self.graph).stream(init_agent_state, **args):
                    for node_name in chunk.keys():
                        if not node_name.startswith("__"):
                            if current_node_name and current_node_start:
                                elapsed = time.time() - current_node_start
                                node_timings[current_node_name] = elapsed
                                logger.info(
                                    f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒"
                                )

                            current_node_name = node_name
                            current_node_start = time.time()
                            break

                    if final_state is None:
                        final_state = init_agent_state.copy()
                    for node_name, node_update in chunk.items():
                        if not node_name.startswith("__"):
                            final_state.update(node_update)
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.graph = self.workflow.compile()

        # 记录最后一个节点的时间
        if current_node_name and current_node_start:
            elapsed = time.time() - current_node_start
            node_timings[current_node_name] = elapsed
            logger.info(f"⏱️ [{current_node_name}] 耗时: {elapsed:.2f}秒")

        # 计算总时间
        total_elapsed = time.time() - total_start_time

        # 调试日志
        logger.info(f"🔍 [TIMING DEBUG] 节点计时数量: {len(node_timings)}")
        logger.info(f"🔍 [TIMING DEBUG] 总耗时: {total_elapsed:.2f}秒")
        logger.info(f"🔍 [TIMING DEBUG] 节点列表: {list(node_timings.keys())}")

        # 打印详细的时间统计
        logger.info("🔍 [TIMING DEBUG] 准备调用 _print_timing_summary")
        self._print_timing_summary(node_timings, total_elapsed)
        logger.info("🔍 [TIMING DEBUG] _print_timing_summary 调用完成")

        if final_state is None:
            raise RuntimeError("图执行未产生最终状态")

        # 构建性能数据
        performance_data = self._build_performance_data(node_timings, total_elapsed)

        # 将性能数据添加到状态中
        final_state["performance_metrics"] = performance_data

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=str(trade_date),
            final_trade_decision=final_state["final_trade_decision"],
        )

        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date)
            )

        # 获取模型信息
        model_info = ""
        try:
            if hasattr(self.deep_thinking_llm, "model_name"):
                model_info = f"{self.deep_thinking_llm.__class__.__name__}:{self.deep_thinking_llm.model_name}"
            else:
                model_info = self.deep_thinking_llm.__class__.__name__
        except Exception:
            model_info = "Unknown"

        # 处理决策并添加模型信息
        decision = self.process_signal(
            final_state["final_trade_decision"], company_name
        )
        decision["model_info"] = model_info

        # Return decision and processed signal
        return final_state, decision

    def _send_progress_update(self, chunk, progress_callback):
        """发送进度更新到回调函数

        LangGraph stream 返回的 chunk 格式：{node_name: {...}}
        节点名称示例：
        - "Market Analyst", "Fundamentals Analyst", "News Analyst", "Social Analyst"
        - "tools_market", "tools_fundamentals", "tools_news", "tools_social"
        - "Msg Clear Market", "Msg Clear Fundamentals", etc.
        - "Bull Researcher", "Bear Researcher", "Research Manager"
        - "Trader"
        - "Risky Analyst", "Safe Analyst", "Neutral Analyst", "Risk Judge", "Portfolio Manager"
        """
        try:
            # 从chunk中提取当前执行的节点信息
            if not isinstance(chunk, dict):
                return

            # 获取第一个非特殊键作为节点名
            node_name = None
            for key in chunk.keys():
                if not key.startswith("__"):
                    node_name = key
                    break

            if not node_name:
                return

            logger.info(f"🔍 [Progress] 节点名称: {node_name}")

            # 检查是否为结束节点
            if "__end__" in chunk:
                logger.info("📊 [Progress] 检测到__end__节点")
                progress_callback("📊 生成报告")
                return

            # 节点名称映射表（匹配 LangGraph 实际节点名）
            node_mapping = {
                # 分析师节点
                "Market Analyst": "📊 市场分析师",
                "Fundamentals Analyst": "💼 基本面分析师",
                "News Analyst": "📰 新闻分析师",
                "Social Analyst": "💬 社交媒体分析师",
                # 工具节点（不发送进度更新，避免重复）
                "tools_market": None,
                "tools_fundamentals": None,
                "tools_news": None,
                "tools_social": None,
                # 消息清理节点（不发送进度更新）
                "Msg Clear Market": None,
                "Msg Clear Fundamentals": None,
                "Msg Clear News": None,
                "Msg Clear Social": None,
                # 研究员节点
                "Bull Researcher": "🐂 看涨研究员",
                "Bear Researcher": "🐻 看跌研究员",
                "Research Manager": "👔 研究经理",
                # 交易员节点
                "Trader": "💼 交易员决策",
                # 风险评估节点
                "Risky Analyst": "🔥 激进风险评估",
                "Safe Analyst": "🛡️ 保守风险评估",
                "Neutral Analyst": "⚖️ 中性风险评估",
                "Risk Judge": "🎯 风险经理",
                "Portfolio Manager": "🎯 投资组合经理",
            }

            # 查找映射的消息
            message = node_mapping.get(node_name)

            if message is None:
                # None 表示跳过（工具节点、消息清理节点）
                logger.debug(f"⏭️ [Progress] 跳过节点: {node_name}")
                return

            if message:
                # 发送进度更新
                logger.info(f"📤 [Progress] 发送进度更新: {message}")
                progress_callback(message)
            else:
                # 未知节点，使用节点名称
                logger.warning(f"⚠️ [Progress] 未知节点: {node_name}")
                progress_callback(f"🔍 {node_name}")

        except Exception as e:
            logger.error(f"❌ 进度更新失败: {e}", exc_info=True)

    def _build_performance_data(
        self, node_timings: Dict[str, float], total_elapsed: float
    ) -> Dict[str, Any]:
        """构建性能数据结构

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间

        Returns:
            性能数据字典
        """
        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = {}
        tool_nodes = {}
        msg_clear_nodes = {}
        research_nodes = {}
        trader_nodes = {}
        risk_nodes = {}
        other_nodes = {}

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if (
                "Risky" in node_name
                or "Safe" in node_name
                or "Neutral" in node_name
                or "Risk Judge" in node_name
                or "Portfolio Manager" in node_name
            ):
                risk_nodes[node_name] = elapsed
            # 然后匹配分析师团队
            elif "Analyst" in node_name:
                analyst_nodes[node_name] = elapsed
            # 工具节点
            elif node_name.startswith("tools_"):
                tool_nodes[node_name] = elapsed
            # 消息清理节点
            elif node_name.startswith("Msg Clear"):
                msg_clear_nodes[node_name] = elapsed
            # 研究团队
            elif "Researcher" in node_name or "Research Manager" in node_name:
                research_nodes[node_name] = elapsed
            # 交易团队
            elif "Trader" in node_name:
                trader_nodes[node_name] = elapsed
            # 其他节点
            else:
                other_nodes[node_name] = elapsed

        # 计算统计数据
        slowest_node = (
            max(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        )
        fastest_node = (
            min(node_timings.items(), key=lambda x: x[1]) if node_timings else (None, 0)
        )
        avg_time = sum(node_timings.values()) / len(node_timings) if node_timings else 0

        return {
            "total_time": round(total_elapsed, 2),
            "total_time_minutes": round(total_elapsed / 60, 2),
            "node_count": len(node_timings),
            "average_node_time": round(avg_time, 2),
            "slowest_node": {"name": slowest_node[0], "time": round(slowest_node[1], 2)}
            if slowest_node[0]
            else None,
            "fastest_node": {"name": fastest_node[0], "time": round(fastest_node[1], 2)}
            if fastest_node[0]
            else None,
            "node_timings": {k: round(v, 2) for k, v in node_timings.items()},
            "category_timings": {
                "analyst_team": {
                    "nodes": {k: round(v, 2) for k, v in analyst_nodes.items()},
                    "total": round(sum(analyst_nodes.values()), 2),
                    "percentage": round(
                        sum(analyst_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "tool_calls": {
                    "nodes": {k: round(v, 2) for k, v in tool_nodes.items()},
                    "total": round(sum(tool_nodes.values()), 2),
                    "percentage": round(
                        sum(tool_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "message_clearing": {
                    "nodes": {k: round(v, 2) for k, v in msg_clear_nodes.items()},
                    "total": round(sum(msg_clear_nodes.values()), 2),
                    "percentage": round(
                        sum(msg_clear_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "research_team": {
                    "nodes": {k: round(v, 2) for k, v in research_nodes.items()},
                    "total": round(sum(research_nodes.values()), 2),
                    "percentage": round(
                        sum(research_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "trader_team": {
                    "nodes": {k: round(v, 2) for k, v in trader_nodes.items()},
                    "total": round(sum(trader_nodes.values()), 2),
                    "percentage": round(
                        sum(trader_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "risk_management_team": {
                    "nodes": {k: round(v, 2) for k, v in risk_nodes.items()},
                    "total": round(sum(risk_nodes.values()), 2),
                    "percentage": round(
                        sum(risk_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
                "other": {
                    "nodes": {k: round(v, 2) for k, v in other_nodes.items()},
                    "total": round(sum(other_nodes.values()), 2),
                    "percentage": round(
                        sum(other_nodes.values()) / total_elapsed * 100, 1
                    )
                    if total_elapsed > 0
                    else 0,
                },
            },
            "llm_config": {
                "provider": self.config.get("llm_provider", "unknown"),
                "deep_think_model": self.config.get("deep_think_llm", "unknown"),
                "quick_think_model": self.config.get("quick_think_llm", "unknown"),
            },
        }

    def _print_timing_summary(
        self, node_timings: Dict[str, float], total_elapsed: float
    ):
        """打印详细的时间统计报告

        Args:
            node_timings: 每个节点的执行时间字典
            total_elapsed: 总执行时间
        """
        logger.info("🔍 [_print_timing_summary] 方法被调用")
        logger.info(
            "🔍 [_print_timing_summary] node_timings 数量: " + str(len(node_timings))
        )
        logger.info("🔍 [_print_timing_summary] total_elapsed: " + str(total_elapsed))

        logger.info("=" * 80)
        logger.info("⏱️  分析性能统计报告")
        logger.info("=" * 80)

        # 节点分类（注意：风险管理节点要先于分析师节点判断，因为它们也包含'Analyst'）
        analyst_nodes = []
        tool_nodes = []
        msg_clear_nodes = []
        research_nodes = []
        trader_nodes = []
        risk_nodes = []
        other_nodes = []

        for node_name, elapsed in node_timings.items():
            # 优先匹配风险管理团队（因为它们也包含'Analyst'）
            if (
                "Risky" in node_name
                or "Safe" in node_name
                or "Neutral" in node_name
                or "Risk Judge" in node_name
                or "Portfolio Manager" in node_name
            ):
                risk_nodes.append((node_name, elapsed))
            # 然后匹配分析师团队
            elif "Analyst" in node_name:
                analyst_nodes.append((node_name, elapsed))
            # 工具节点
            elif node_name.startswith("tools_"):
                tool_nodes.append((node_name, elapsed))
            # 消息清理节点
            elif node_name.startswith("Msg Clear"):
                msg_clear_nodes.append((node_name, elapsed))
            # 研究团队
            elif "Researcher" in node_name or "Research Manager" in node_name:
                research_nodes.append((node_name, elapsed))
            # 交易团队
            elif "Trader" in node_name:
                trader_nodes.append((node_name, elapsed))
            # 其他节点
            else:
                other_nodes.append((node_name, elapsed))

        # 打印分类统计
        def print_category(title: str, nodes: List[Tuple[str, float]]):
            if not nodes:
                return
            logger.info(f"\n📊 {title}")
            logger.info("-" * 80)
            total_category_time = sum(t for _, t in nodes)
            for node_name, elapsed in sorted(nodes, key=lambda x: x[1], reverse=True):
                percentage = (elapsed / total_elapsed * 100) if total_elapsed > 0 else 0
                logger.info(
                    f"  • {node_name:40s} {elapsed:8.2f}秒  ({percentage:5.1f}%)"
                )
            logger.info(
                f"  {'小计':40s} {total_category_time:8.2f}秒  ({total_category_time / total_elapsed * 100:5.1f}%)"
            )

        print_category("分析师团队", analyst_nodes)
        print_category("工具调用", tool_nodes)
        print_category("消息清理", msg_clear_nodes)
        print_category("研究团队", research_nodes)
        print_category("交易团队", trader_nodes)
        print_category("风险管理团队", risk_nodes)
        print_category("其他节点", other_nodes)

        # 打印总体统计
        logger.info("\n" + "=" * 80)
        logger.info(
            f"🎯 总执行时间: {total_elapsed:.2f}秒 ({total_elapsed / 60:.2f}分钟)"
        )
        logger.info(f"📈 节点总数: {len(node_timings)}")
        if node_timings:
            avg_time = sum(node_timings.values()) / len(node_timings)
            logger.info(f"⏱️  平均节点耗时: {avg_time:.2f}秒")
            slowest_node = max(node_timings.items(), key=lambda x: x[1])
            logger.info(f"🐌 最慢节点: {slowest_node[0]} ({slowest_node[1]:.2f}秒)")
            fastest_node = min(node_timings.items(), key=lambda x: x[1])
            logger.info(f"⚡ 最快节点: {fastest_node[0]} ({fastest_node[1]:.2f}秒)")

        # 打印LLM配置信息
        logger.info("\n🤖 LLM配置:")
        logger.info(f"  • 提供商: {self.config.get('llm_provider', 'unknown')}")
        logger.info(f"  • 深度思考模型: {self.config.get('deep_think_llm', 'unknown')}")
        logger.info(
            f"  • 快速思考模型: {self.config.get('quick_think_llm', 'unknown')}"
        )
        logger.info("=" * 80)

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        safe_ticker = safe_ticker_component(str(self.ticker))
        directory = Path("eval_results") / safe_ticker / "TradingAgentsStrategy_logs"
        directory.mkdir(parents=True, exist_ok=True)

        with open(directory / "full_states_log.json", "w", encoding="utf-8") as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update existing CN role memories."""
        if self.bull_memory is not None:
            self.reflector.reflect_bull_researcher(
                self.curr_state, returns_losses, self.bull_memory
            )
        if self.bear_memory is not None:
            self.reflector.reflect_bear_researcher(
                self.curr_state, returns_losses, self.bear_memory
            )
        if self.trader_memory is not None:
            self.reflector.reflect_trader(
                self.curr_state, returns_losses, self.trader_memory
            )
        if self.invest_judge_memory is not None:
            self.reflector.reflect_invest_judge(
                self.curr_state, returns_losses, self.invest_judge_memory
            )
        if self.risk_manager_memory is not None:
            self.reflector.reflect_risk_manager(
                self.curr_state, returns_losses, self.risk_manager_memory
            )

    def process_signal(self, full_signal, stock_symbol=None):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal, stock_symbol)
