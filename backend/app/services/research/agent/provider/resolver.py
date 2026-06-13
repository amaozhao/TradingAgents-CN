from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from app.core.bridge import get_bridged_api_key, get_bridged_model
from app.core.config import settings
from app.core.database import get_postgres_db_sync
from app.core.unified import unified_config

from ..context import ResearchPrincipal
from ..user.model.keys import user_model_key_service


class AgentModelConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentModelConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout_seconds: float = 300.0


@dataclass(frozen=True)
class ProviderCandidate:
    provider: str
    model: str
    info: dict[str, Any]


def is_placeholder(value: str | None) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    return (
        lowered == "your-api-key"
        or lowered.startswith("your_")
        or lowered.startswith("your-")
        or lowered.endswith("_here")
        or lowered.endswith("-here")
        or len(cleaned) <= 10
    )


def first_configured_text(*values: str | None) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and not is_placeholder(cleaned):
            return cleaned
    return ""


def first_configured_model_text(*values: str | None) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        lowered = cleaned.lower()
        if (
            cleaned
            and lowered != "your-api-key"
            and not lowered.startswith("your_")
            and not lowered.startswith("your-")
            and not lowered.endswith("_here")
            and not lowered.endswith("-here")
        ):
            return cleaned
    return ""


def split_provider_model(value: str) -> tuple[str | None, str]:
    cleaned = value.strip()
    if "/" in cleaned:
        provider, model = cleaned.split("/", 1)
        provider = provider.strip().lower()
        model = model.strip()
    else:
        provider = None
        model = cleaned
    if not model or (provider is not None and not provider):
        raise AgentModelConfigurationError(
            "Agent 默认模型格式无效，应为 provider/model"
        )
    return provider, model


def provider_info_for_model(model: str) -> dict[str, Any]:
    from app.services.analysis.simple.provider import get_provider_and_url_by_model_sync

    return get_provider_and_url_by_model_sync(model)


class ProviderCatalog:
    def __init__(
        self, *, db_sync_loader: Callable[[], Any] = get_postgres_db_sync
    ) -> None:
        self._db_sync_loader = db_sync_loader

    def default_agent_model(self) -> str:
        return first_configured_model_text(
            settings.TRADING_AGENTS_DEFAULT_MODEL,
            get_bridged_model("default"),
            settings.TRADING_AGENTS_QUICK_MODEL,
            get_bridged_model("quick"),
            unified_config.get_default_model(),
            unified_config.get_quick_analysis_model(),
        )

    def minimax_token_plan_base_url(self, configured_base_url: str = "") -> str:
        base_url = str(
            configured_base_url or "https://api.minimaxi.com/anthropic"
        ).rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme != "https":
            raise AgentModelConfigurationError(
                "MiniMax Token Plan base URL 必须使用 HTTPS"
            )
        if parsed.hostname not in {"api.minimaxi.com", "api.minimax.io"}:
            raise AgentModelConfigurationError(
                "MiniMax Token Plan base URL 仅允许 api.minimaxi.com 或 api.minimax.io"
            )
        if not parsed.path.startswith("/anthropic"):
            raise AgentModelConfigurationError(
                "MiniMax Token Plan base URL 必须指向 /anthropic 路径"
            )
        return base_url

    def provider_base_url(self, provider: str, configured_base_url: str = "") -> str:
        provider = provider.lower()
        if provider == "minimax-token-plan":
            return self.minimax_token_plan_base_url(configured_base_url)
        if configured_base_url:
            return configured_base_url.rstrip("/")
        if provider == "openai":
            return (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        if provider == "deepseek":
            return (settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip(
                "/"
            )
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        if provider in {"dashscope", "qwen"}:
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if provider == "minimax":
            return "https://api.minimax.io/v1"
        if provider in {"anthropic", "claude"}:
            return "https://api.anthropic.com"
        if provider == "custom":
            return settings.CUSTOM_OPENAI_BASE_URL.rstrip("/")
        raise AgentModelConfigurationError(f"不支持的 Agent 模型提供方: {provider}")

    def candidate_backend_url(
        self,
        provider: str,
        configured_base_url: str = "",
        provider_default_base_url: str = "",
    ) -> str:
        provider = provider.lower()
        configured = str(configured_base_url or "").strip()
        provider_default = str(provider_default_base_url or "").strip()
        if provider != "minimax-token-plan":
            return configured or provider_default
        if configured:
            try:
                return self.minimax_token_plan_base_url(configured)
            except AgentModelConfigurationError:
                if provider_default:
                    return provider_default
                raise
        return provider_default

    def provider_env_key(self, provider: str) -> str:
        provider = provider.lower()
        bridged_key = get_bridged_api_key(provider)
        if not bridged_key and provider in {"dashscope", "qwen"}:
            bridged_key = get_bridged_api_key("dashscope") or get_bridged_api_key(
                "qwen"
            )
        if not is_placeholder(bridged_key):
            return str(bridged_key)
        if provider == "minimax-token-plan":
            return settings.text_value("MINIMAX_TOKEN_PLAN_API_KEY")
        if provider == "minimax":
            return settings.text_value("MINIMAX_API_KEY")
        if provider in {"anthropic", "claude"}:
            return (
                ""
                if is_placeholder(settings.ANTHROPIC_API_KEY)
                else settings.ANTHROPIC_API_KEY
            )
        if provider == "openai":
            return (
                ""
                if is_placeholder(settings.OPENAI_API_KEY)
                else settings.OPENAI_API_KEY
            )
        if provider == "deepseek":
            return (
                ""
                if is_placeholder(settings.DEEPSEEK_API_KEY)
                else settings.DEEPSEEK_API_KEY
            )
        if provider == "openrouter":
            return (
                ""
                if is_placeholder(settings.OPENROUTER_API_KEY)
                else settings.OPENROUTER_API_KEY
            )
        if provider in {"dashscope", "qwen"}:
            return (
                ""
                if is_placeholder(settings.DASHSCOPE_API_KEY)
                else settings.DASHSCOPE_API_KEY
            )
        if provider == "custom":
            return (
                ""
                if is_placeholder(settings.CUSTOM_OPENAI_API_KEY)
                else settings.CUSTOM_OPENAI_API_KEY
            )
        return ""

    def configured_candidate_models(self) -> list[ProviderCandidate]:
        candidates: list[ProviderCandidate] = []
        seen: set[tuple[str, str]] = set()
        try:
            db = self._db_sync_loader()
            system = (
                db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
                or {}
            )
            providers = {
                str(item.get("name") or "").strip().lower(): item
                for item in db.llm_providers.find({})
            }
            for item in system.get("llm_configs", []):
                if not item.get("enabled"):
                    continue
                model = str(item.get("model_name") or "").strip()
                provider = str(item.get("provider") or "").strip().lower()
                if not model or not provider:
                    continue
                key = (provider, model)
                if key in seen:
                    continue
                seen.add(key)
                provider_doc = providers.get(provider) or providers.get(
                    "qwen" if provider == "dashscope" else provider
                )
                candidates.append(
                    ProviderCandidate(
                        provider=provider,
                        model=model,
                        info={
                            "provider": provider,
                            "api_key": item.get("api_key")
                            or (provider_doc or {}).get("api_key")
                            or "",
                            "backend_url": self.candidate_backend_url(
                                provider,
                                str(item.get("api_base") or ""),
                                str((provider_doc or {}).get("default_base_url") or ""),
                            ),
                        },
                    )
                )

            minimax_provider = providers.get("minimax-token-plan")
            if minimax_provider and ("minimax-token-plan", "MiniMax-M3") not in seen:
                minimax_key = minimax_provider.get("api_key") or self.provider_env_key(
                    "minimax-token-plan"
                )
                candidates.append(
                    ProviderCandidate(
                        provider="minimax-token-plan",
                        model="MiniMax-M3",
                        info={
                            "provider": "minimax-token-plan",
                            "api_key": minimax_key,
                            "backend_url": minimax_provider.get("default_base_url")
                            or "",
                        },
                    )
                )
        except Exception:
            return candidates
        return candidates

    def fallback_configured_model(self) -> ProviderCandidate | None:
        for candidate in self.configured_candidate_models():
            api_key = first_configured_text(
                str(candidate.info.get("api_key") or ""),
                self.provider_env_key(candidate.provider),
            )
            if api_key:
                return ProviderCandidate(
                    provider=candidate.provider,
                    model=candidate.model,
                    info={**candidate.info, "api_key": api_key},
                )
        return None

    def safe_provider_model(self, value: str) -> tuple[str, str]:
        try:
            provider, model = split_provider_model(value)
            if provider is None:
                provider_info = provider_info_for_model(model)
                provider = str(provider_info.get("provider") or "").strip().lower()
            return provider or "", model
        except Exception:
            return "", value


class ProviderResolver:
    def __init__(self, catalog: ProviderCatalog | None = None) -> None:
        self.catalog = catalog or ProviderCatalog()

    def default_agent_model(self) -> str:
        return self.catalog.default_agent_model()

    def fallback_configured_model(self) -> ProviderCandidate | None:
        return self.catalog.fallback_configured_model()

    async def describe_agent_model_resolution(
        self, principal: ResearchPrincipal
    ) -> dict[str, Any]:
        default_model = self.default_agent_model()
        default_provider = ""
        default_model_name = ""
        default_has_key = False
        default_error = ""
        if default_model:
            default_provider, default_model_name = self.catalog.safe_provider_model(
                default_model
            )
            if default_provider:
                try:
                    provider_info = (
                        provider_info_for_model(default_model_name)
                        if "/" not in default_model
                        else {}
                    )
                    user_key = await user_model_key_service.resolve_key_for_agent(
                        user_id=principal.user_id,
                        provider=default_provider,
                        model=default_model_name,
                    )
                    default_has_key = bool(
                        first_configured_text(
                            user_key,
                            str(provider_info.get("api_key") or ""),
                            self.catalog.provider_env_key(default_provider),
                        )
                    )
                except Exception as exc:
                    default_error = str(exc)

        candidates = []
        for candidate in self.catalog.configured_candidate_models():
            has_key = bool(
                first_configured_text(
                    str(candidate.info.get("api_key") or ""),
                    self.catalog.provider_env_key(candidate.provider),
                )
            )
            candidates.append(
                {
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "has_valid_key": has_key,
                    "base_url_configured": bool(
                        str(candidate.info.get("backend_url") or "").strip()
                    ),
                }
            )

        fallback = self.fallback_configured_model()
        effective_provider = ""
        effective_model = ""
        effective_base_url = ""
        status = "missing_key"
        reason = "未检测到任何可用 Agent 模型 API Key"
        if default_provider and default_model_name and default_has_key:
            effective_provider = default_provider
            effective_model = default_model_name
            status = "configured"
            reason = "默认 Agent 模型已配置有效 API Key"
        elif fallback:
            effective_provider = fallback.provider
            effective_model = fallback.model
            status = "fallback_configured"
            reason = (
                f"默认 Agent 模型 {default_provider}/{default_model_name} 无有效 API Key，"
                f"已切换到 {effective_provider}/{effective_model}"
            )
            try:
                effective_base_url = self.catalog.provider_base_url(
                    effective_provider,
                    str(fallback.info.get("backend_url") or ""),
                )
            except Exception as exc:
                status = "invalid_base_url"
                reason = str(exc)

        if effective_provider and not effective_base_url:
            try:
                effective_base_url = self.catalog.provider_base_url(effective_provider)
            except Exception as exc:
                status = "invalid_base_url"
                reason = str(exc)

        return {
            "status": status,
            "reason": reason,
            "default_model": default_model,
            "default_provider": default_provider,
            "default_model_name": default_model_name,
            "default_has_valid_key": default_has_key,
            "default_resolution_error": default_error,
            "effective_provider": effective_provider,
            "effective_model": effective_model,
            "effective_base_url": effective_base_url,
            "candidate_models": candidates,
            "secrets": "redacted",
        }

    async def resolve_agent_model_config(
        self, principal: ResearchPrincipal
    ) -> AgentModelConfig:
        provider_info: dict[str, Any] = {}
        default_model = self.default_agent_model()
        if default_model:
            provider, model = split_provider_model(default_model)
        else:
            fallback = self.fallback_configured_model()
            provider = fallback.provider if fallback else ""
            model = fallback.model if fallback else ""
            provider_info = fallback.info if fallback else {}
            if not provider or not model:
                raise AgentModelConfigurationError(
                    "未配置可用的 Agent 模型 API Key；请在 MiniMax Token Plan、DeepSeek、Qwen 或其他启用模型中配置有效密钥"
                )
        if provider is None:
            provider_info = provider_info_for_model(model)
            provider = str(provider_info.get("provider") or "").strip().lower()
        if not provider:
            raise AgentModelConfigurationError(f"未找到 Agent 模型 {model} 的提供方")
        api_key = await user_model_key_service.resolve_key_for_agent(
            user_id=principal.user_id,
            provider=provider,
            model=model,
        )
        api_key = first_configured_text(
            api_key,
            str(provider_info.get("api_key") or ""),
            self.catalog.provider_env_key(provider),
        )
        if not api_key:
            fallback = self.fallback_configured_model()
            if fallback:
                provider = fallback.provider
                model = fallback.model
                provider_info = fallback.info
                api_key = str(provider_info.get("api_key") or "")
        if not api_key:
            raise AgentModelConfigurationError(
                f"默认 Agent 模型 {provider}/{model} 没有有效 API Key，且未检测到 MiniMax Token Plan、DeepSeek、Qwen 等任何可用模型密钥；请确认设置页已保存到后端或系统环境变量已生效"
            )
        base_url = self.catalog.provider_base_url(
            provider, str(provider_info.get("backend_url") or "")
        )
        if not base_url:
            raise AgentModelConfigurationError(
                f"未配置 {provider}/{model} 的 API 基础地址"
            )
        return AgentModelConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
