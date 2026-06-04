# ruff: noqa: F403,F405
from .common import *


class ProviderModelMixin:
    async def fetch_provider_models(
        self, provider_id: str, filters: Optional[dict] = None
    ) -> dict:
        """从厂家 API 获取模型列表"""
        try:
            logger.info(f"🔍 [fetch_provider_models] provider_id={provider_id}")

            db = await self._get_db()
            providers_collection = db.llm_providers

            # 兼容处理：尝试 DocumentId 和字符串两种类型
            DocumentId = getattr(importlib.import_module("app.db.ids"), "DocumentId")
            provider_data = None
            try:
                provider_data = await providers_collection.find_one(
                    {"_id": DocumentId(provider_id)}
                )
            except Exception:
                pass

            if not provider_data:
                provider_data = await providers_collection.find_one(
                    {"_id": provider_id}
                )

            if not provider_data:
                return {"success": False, "message": f"厂家不存在 (ID: {provider_id})"}

            provider_name = str(provider_data.get("name") or "")
            api_key = str(provider_data.get("api_key") or "")
            base_url = str(provider_data.get("default_base_url") or "")
            display_name = str(provider_data.get("display_name") or provider_name)
            normalized_provider_name = normalize_provider_key(provider_name)
            filters = filters or {}

            logger.info(
                "🔍 [fetch_provider_models] provider loaded: "
                f"name={provider_name}, normalized={normalized_provider_name}, "
                f"display_name={display_name}, base_url={base_url}, "
                f"filters={filters}"
            )

            # 🔥 判断数据库中的 API Key 是否有效
            if not self._is_valid_api_key(api_key):
                # 数据库中的 Key 无效，尝试从环境变量读取
                env_api_key = self._get_env_api_key(provider_name)
                if env_api_key:
                    api_key = env_api_key
                    logger.info(
                        f"✅ [fetch_provider_models] 数据库配置无效，从环境变量读取到 {display_name} 的 API Key"
                    )
                else:
                    # 某些聚合平台（如 OpenRouter）的 /models 端点不需要 API Key
                    logger.warning(
                        f"⚠️ [fetch_provider_models] {display_name} 未配置有效的API密钥，尝试无认证访问"
                    )
            else:
                logger.info(
                    f"✅ [fetch_provider_models] 使用数据库配置的 {display_name} API密钥"
                )

            if not base_url:
                return {
                    "success": False,
                    "message": f"{display_name} 未配置 API 基础地址 (default_base_url)",
                }

            if self._is_aihubmix_provider(provider_name, base_url):
                logger.info("🧭 [fetch_provider_models] branch=aihubmix")
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._fetch_aihubmix_models,
                    api_key,
                    base_url,
                    display_name,
                    filters,
                )
            else:
                logger.warning(
                    "🧭 [fetch_provider_models] branch=generic_openai_compatible "
                    f"(provider_name={provider_name}, normalized={normalized_provider_name}, base_url={base_url})"
                )
                # 调用 OpenAI 兼容的 /v1/models 端点
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_models_from_api, api_key, base_url, display_name
                )

            logger.info(
                "📦 [fetch_provider_models] result "
                f"success={result.get('success')} "
                f"models={len(result.get('models') or [])} "
                f"message={result.get('message')}"
            )
            return result

        except Exception as e:
            logger.exception(f"❌ [fetch_provider_models] 获取模型列表失败: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()
            return {"success": False, "message": f"获取模型列表失败: {str(e)}"}

    def _is_aihubmix_provider(
        self, provider_name: str | None, base_url: str | None
    ) -> bool:
        normalized_name = normalize_provider_key(provider_name or "")
        base_url_lower = str(base_url or "").lower()
        return (
            normalized_name == "aihubmix"
            or "aihubmix.com" in base_url_lower
            or "api.aihubmix.com" in base_url_lower
        )

    def _fetch_models_from_api(
        self, api_key: str, base_url: str, display_name: str
    ) -> dict:
        """从 API 获取模型列表"""
        try:
            requests = importlib.import_module("requests")

            # 🔧 智能版本号处理：只有在没有版本号的情况下才添加 /v1
            # 避免对已有版本号的URL（如智谱AI的 /v4）重复添加 /v1
            re = importlib.import_module("re")
            base_url = base_url.rstrip("/")
            if not re.search(r"/v\d+$", base_url):
                # URL末尾没有版本号，添加 /v1（OpenAI标准）
                base_url = base_url + "/v1"
                logger.info(f"   [获取模型列表] 添加 /v1 版本号: {base_url}")
            else:
                # URL已包含版本号（如 /v4），不添加
                logger.info(f"   [获取模型列表] 检测到已有版本号，保持原样: {base_url}")

            url = f"{base_url}/models"

            # 构建请求头
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                print(f"🔍 请求 URL: {url} (with API Key)")
            else:
                print(f"🔍 请求 URL: {url} (without API Key)")

            response = requests.get(url, headers=headers, timeout=15)

            print(f"📊 响应状态码: {response.status_code}")
            print(f"📊 响应内容: {response.text[:500]}...")

            if response.status_code == 200:
                result = response.json()
                print(f"📊 响应 JSON 结构: {list(result.keys())}")

                if "data" in result and isinstance(result["data"], list):
                    all_models = result["data"]
                    print(f"📊 API 返回 {len(all_models)} 个模型")

                    # 打印前几个模型的完整结构（用于调试价格字段）
                    if all_models:
                        print("🔍 第一个模型的完整结构:")
                        json = importlib.import_module("json")
                        print(json.dumps(all_models[0], indent=2, ensure_ascii=False))

                    # 打印所有 Anthropic 模型（用于调试）
                    anthropic_models = [
                        m for m in all_models if "anthropic" in m.get("id", "").lower()
                    ]
                    if anthropic_models:
                        print(f"🔍 Anthropic 模型列表 ({len(anthropic_models)} 个):")
                        for m in anthropic_models[:20]:  # 只打印前 20 个
                            print(f"   - {m.get('id')}")

                    # 过滤：只保留主流大厂的常用模型
                    filtered_models = self._filter_popular_models(all_models)
                    print(f"✅ 过滤后保留 {len(filtered_models)} 个常用模型")

                    # 转换模型格式，包含价格信息
                    formatted_models = self._format_models_with_pricing(filtered_models)

                    return {
                        "success": True,
                        "models": formatted_models,
                        "message": f"成功获取 {len(formatted_models)} 个常用模型（已过滤）",
                    }
                else:
                    print("❌ 响应格式异常，期望 'data' 字段为列表")
                    return {
                        "success": False,
                        "message": f"{display_name} API 响应格式异常（缺少 data 字段或格式不正确）",
                    }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": f"{display_name} API密钥无效或已过期",
                }
            elif response.status_code == 403:
                return {"success": False, "message": f"{display_name} API权限不足"}
            else:
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get("error", {}).get(
                        "message", f"HTTP {response.status_code}"
                    )
                    print(f"❌ API 错误: {error_msg}")
                    return {
                        "success": False,
                        "message": f"{display_name} API请求失败: {error_msg}",
                    }
                except Exception:
                    print(f"❌ HTTP 错误: {response.status_code}")
                    return {
                        "success": False,
                        "message": f"{display_name} API请求失败: HTTP {response.status_code}, 响应: {response.text[:200]}",
                    }

        except Exception as e:
            print(f"❌ 异常: {e}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()
            return {
                "success": False,
                "message": f"{display_name} API请求异常: {str(e)}",
            }

    def _fetch_aihubmix_models(
        self, api_key: str, base_url: str, display_name: str, filters: dict
    ) -> dict:
        """从 AiHubMix 的 Models API 获取模型列表。"""
        try:
            requests = importlib.import_module("requests")

            root_url = re.sub(r"/v\d+$", "", base_url.rstrip("/"))
            url = f"{root_url}/api/v1/models"

            params = {
                "type": filters.get("type") or "llm",
                "modalities": filters.get("modalities") or "text",
                "sort_by": filters.get("sort_by") or "order",
                "sort_order": filters.get("sort_order") or "asc",
            }

            features = filters.get("features")
            if features:
                if isinstance(features, list):
                    params["features"] = ",".join(
                        [str(item).strip() for item in features if str(item).strip()]
                    )
                elif str(features).strip():
                    params["features"] = str(features).strip()

            model_keyword = filters.get("model_keyword")
            if model_keyword and str(model_keyword).strip():
                params["model"] = str(model_keyword).strip()

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            logger.info(
                f"🔍 [AiHubMix] 请求模型列表: url={url} params={params} "
                f"provider_names={filters.get('provider_names')} limit={filters.get('limit')}"
            )
            response = requests.get(url, headers=headers, params=params, timeout=20)
            logger.info(f"📡 [AiHubMix] HTTP {response.status_code}")

            if response.status_code != 200:
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get("error", {}).get(
                        "message", f"HTTP {response.status_code}"
                    )
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                return {
                    "success": False,
                    "message": f"{display_name} API请求失败: {error_msg}",
                }

            result = response.json()
            if "data" not in result or not isinstance(result["data"], list):
                return {
                    "success": False,
                    "message": f"{display_name} API 响应格式异常（缺少 data 字段或格式不正确）",
                }

            all_models = result["data"]
            logger.info(
                "📊 [AiHubMix] 原始模型数量=%s, 前10个=%s",
                len(all_models),
                [
                    str(item.get("model_id") or item.get("id") or "")
                    for item in all_models[:10]
                ],
            )
            filtered_models = self._filter_aihubmix_models(all_models, filters)
            logger.info(
                "📊 [AiHubMix] 过滤后模型数量=%s, 前10个=%s",
                len(filtered_models),
                [
                    str(item.get("model_id") or item.get("id") or "")
                    for item in filtered_models[:10]
                ],
            )
            formatted_models = self._format_aihubmix_models(filtered_models)

            return {
                "success": True,
                "models": formatted_models,
                "message": f"成功获取 {len(formatted_models)} 个 AiHubMix 模型（已过滤，原始 {len(all_models)} 个）",
            }
        except Exception as e:
            logger.exception("AiHubMix 模型列表获取失败")
            return {
                "success": False,
                "message": f"{display_name} API请求异常: {str(e)}",
            }

    def _filter_aihubmix_models(self, models: list, filters: dict) -> list:
        """过滤 AiHubMix 模型，避免一次导入过多低价值模型。"""
        limit = self._safe_int(filters.get("limit"), default=40)
        recommended_only = bool(filters.get("recommended_only", False))
        tools_only = bool(filters.get("tools_only", False))
        exclude_preview = bool(filters.get("exclude_preview", True))
        keyword = str(filters.get("model_keyword") or "").strip().lower()
        provider_names = {
            str(item).strip().lower()
            for item in (filters.get("provider_names") or [])
            if str(item).strip()
        }

        requested_modalities = {
            item.strip().lower()
            for item in str(filters.get("modalities") or "text").split(",")
            if item.strip()
        }

        raw_features = filters.get("features")
        if isinstance(raw_features, list):
            requested_features = {
                str(item).strip().lower() for item in raw_features if str(item).strip()
            }
        else:
            requested_features = {
                item.strip().lower()
                for item in str(raw_features or "").split(",")
                if item.strip()
            }

        preferred_prefixes = (
            "gpt-",
            "o1",
            "o3",
            "o4",
            "claude-",
            "gemini",
            "deepseek-",
            "qwen-",
            "glm-",
            "kimi-",
        )
        excluded_keywords = (
            "preview",
            "experimental",
            "exp",
            "alpha",
            "beta",
            "test",
            "free",
        )

        filtered = []
        drop_reasons = defaultdict(int)
        for model in models:
            model_id = str(model.get("model_id") or model.get("id") or "").strip()
            if not model_id:
                drop_reasons["empty_model_id"] += 1
                continue

            model_id_lower = model_id.lower()
            provider_vendor = self._infer_aihubmix_model_provider(model_id_lower)
            model_type = str(model.get("types") or "").strip().lower()
            features = {
                item.strip().lower()
                for item in str(model.get("features") or "").split(",")
                if item.strip()
            }
            modalities = {
                item.strip().lower()
                for item in str(model.get("input_modalities") or "").split(",")
                if item.strip()
            }

            if model_type and model_type != "llm":
                drop_reasons["non_llm"] += 1
                continue
            if requested_modalities and not requested_modalities.issubset(modalities):
                drop_reasons["modalities_mismatch"] += 1
                continue
            if requested_features and not requested_features.issubset(features):
                drop_reasons["features_mismatch"] += 1
                continue
            if tools_only and not ({"tools", "function_calling"} & features):
                drop_reasons["tools_only_mismatch"] += 1
                continue
            if keyword and keyword not in model_id_lower:
                drop_reasons["keyword_mismatch"] += 1
                continue
            if exclude_preview and any(
                word in model_id_lower for word in excluded_keywords
            ):
                drop_reasons["preview_excluded"] += 1
                continue
            if recommended_only and not model_id_lower.startswith(preferred_prefixes):
                drop_reasons["not_recommended"] += 1
                continue
            if provider_names and provider_vendor not in provider_names:
                drop_reasons[f"provider_mismatch:{provider_vendor}"] += 1
                continue

            filtered.append(model)

        filtered.sort(key=self._aihubmix_model_sort_key)
        logger.info(
            "🧪 [AiHubMix] filter summary: total=%s kept=%s provider_names=%s drop_reasons=%s",
            len(models),
            len(filtered),
            sorted(provider_names),
            dict(sorted(drop_reasons.items(), key=lambda item: (-item[1], item[0]))),
        )
        return filtered[:limit]

    def _aihubmix_model_sort_key(self, model: dict) -> tuple:
        model_id = str(model.get("model_id") or model.get("id") or "").lower()
        features = {
            item.strip().lower()
            for item in str(model.get("features") or "").split(",")
            if item.strip()
        }
        pricing = model.get("pricing") or {}
        input_price = self._safe_float(pricing.get("input"), default=999999.0)
        context_length = self._safe_int(model.get("context_length"), default=0) or 0
        has_tools = 0 if ({"tools", "function_calling"} & features) else 1
        mainstream_rank = (
            0
            if model_id.startswith(
                ("gpt-", "claude-", "gemini", "deepseek-", "qwen-", "glm-", "kimi-")
            )
            else 1
        )
        return (has_tools, mainstream_rank, -context_length, input_price, model_id)

    def _format_aihubmix_models(self, models: list) -> list:
        formatted = []
        for model in models:
            model_id = str(model.get("model_id") or model.get("id") or "").strip()
            pricing = model.get("pricing") or {}
            formatted.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "provider_vendor": self._infer_aihubmix_model_provider(model_id),
                    "description": model.get("desc"),
                    "context_length": self._safe_int(model.get("context_length")),
                    "max_tokens": self._safe_int(model.get("max_output")),
                    "input_price_per_1k": self._safe_float(pricing.get("input")),
                    "output_price_per_1k": self._safe_float(pricing.get("output")),
                    "currency": "USD",
                    "capabilities": [
                        item.strip()
                        for item in str(model.get("features") or "").split(",")
                        if item.strip()
                    ],
                }
            )
        return formatted

    def _infer_aihubmix_model_provider(self, model_id: str) -> str:
        model_id = str(model_id or "").lower()
        provider_prefix_map = [
            (("gpt-", "o1", "o3", "o4", "chatgpt-"), "openai"),
            (("claude-",), "anthropic"),
            (("gemini",), "google"),
            (("deepseek-", "deepseek"), "deepseek"),
            (("qwen-", "qwen"), "qwen"),
            (("glm-", "glm", "chatglm", "zhipu"), "glm"),
            (("kimi-", "kimi", "moonshot"), "kimi"),
            (("doubao-", "doubao"), "doubao"),
            (("minimax-", "minimax", "abab", "mimo-"), "minimax"),
            (("mistral-", "mistral"), "mistral"),
            (("llama-", "meta/", "meta-"), "meta"),
            (("jina-", "jina/"), "jina"),
        ]
        for prefixes, provider in provider_prefix_map:
            if model_id.startswith(prefixes):
                return provider
        return "other"

    def _safe_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _safe_float(
        self, value: Any, default: Optional[float] = None
    ) -> Optional[float]:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _format_models_with_pricing(self, models: list) -> list:
        """
        格式化模型列表，包含价格信息

        支持多种价格格式：
        1. OpenRouter: pricing.prompt/completion (USD per token)
        2. 302.ai: price.prompt/completion 或 price.input/output
        3. 其他: 可能没有价格信息
        """
        formatted = []
        for model in models:
            model_id = model.get("id", "")
            model_name = model.get("name", model_id)

            # 尝试从多个字段获取价格信息
            input_price_per_1k = None
            output_price_per_1k = None

            # 方式1：OpenRouter 格式 (pricing.prompt/completion)
            pricing = model.get("pricing", {})
            if pricing:
                prompt_price = pricing.get("prompt", "0")  # USD per token
                completion_price = pricing.get("completion", "0")  # USD per token

                try:
                    if prompt_price and float(prompt_price) > 0:
                        input_price_per_1k = float(prompt_price) * 1000
                    if completion_price and float(completion_price) > 0:
                        output_price_per_1k = float(completion_price) * 1000
                except (ValueError, TypeError):
                    pass

            # 方式2：302.ai 格式 (price.prompt/completion 或 price.input/output)
            if not input_price_per_1k and not output_price_per_1k:
                price = model.get("price", {})
                if price and isinstance(price, dict):
                    # 尝试 prompt/completion 字段
                    prompt_price = price.get("prompt") or price.get("input")
                    completion_price = price.get("completion") or price.get("output")

                    try:
                        if prompt_price and float(prompt_price) > 0:
                            # 假设是 per token，转换为 per 1K tokens
                            input_price_per_1k = float(prompt_price) * 1000
                        if completion_price and float(completion_price) > 0:
                            output_price_per_1k = float(completion_price) * 1000
                    except (ValueError, TypeError):
                        pass

            # 获取上下文长度
            context_length = model.get("context_length")
            if not context_length:
                # 尝试从 top_provider 获取
                top_provider = model.get("top_provider", {})
                context_length = top_provider.get("context_length")

            # 如果还是没有，尝试从 max_completion_tokens 推断
            if not context_length:
                max_tokens = model.get("max_completion_tokens")
                if max_tokens and max_tokens > 0:
                    # 通常上下文长度是最大输出的 4-8 倍
                    context_length = max_tokens * 4

            formatted_model = {
                "id": model_id,
                "name": model_name,
                "context_length": context_length,
                "input_price_per_1k": input_price_per_1k,
                "output_price_per_1k": output_price_per_1k,
            }

            formatted.append(formatted_model)

            # 打印价格信息（用于调试）
            if input_price_per_1k or output_price_per_1k:
                print(
                    f"💰 {model_id}: 输入=${input_price_per_1k:.6f}/1K, 输出=${output_price_per_1k:.6f}/1K"
                )

        return formatted

    def _filter_popular_models(self, models: list) -> list:
        """过滤模型列表，只保留主流大厂的常用模型"""
        re = importlib.import_module("re")

        # 只保留三大厂：OpenAI、Anthropic、Google
        popular_providers = [
            "openai",  # OpenAI
            "anthropic",  # Anthropic
            "google",  # Google
        ]

        # 常见模型名称前缀（用于识别不带厂商前缀的模型）
        model_prefixes = {
            "gpt-": "openai",  # gpt-3.5-turbo, gpt-4, gpt-4o
            "o1-": "openai",  # o1-preview, o1-mini
            "claude-": "anthropic",  # claude-3-opus, claude-3-sonnet
            "gemini-": "google",  # gemini-pro, gemini-1.5-pro
            "gemini": "google",  # gemini (不带连字符)
        }

        # 排除的关键词
        exclude_keywords = [
            "preview",
            "experimental",
            "alpha",
            "beta",
            "free",
            "extended",
            "nitro",
            ":free",
            ":extended",
            "online",  # 排除带在线搜索的版本
            "instruct",  # 排除 instruct 版本
        ]

        # 日期格式正则表达式（匹配 2024-05-13 这种格式）
        date_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")

        filtered = []
        for model in models:
            model_id = model.get("id", "").lower()
            model_name = model.get("name", "").lower()

            # 检查是否属于三大厂
            # 方式1：模型ID中包含厂商名称（如 openai/gpt-4）
            is_popular_provider = any(
                provider in model_id for provider in popular_providers
            )

            # 方式2：模型ID以常见前缀开头（如 gpt-4, claude-3-sonnet）
            if not is_popular_provider:
                for prefix, provider in model_prefixes.items():
                    if model_id.startswith(prefix):
                        is_popular_provider = True
                        print(f"🔍 识别模型前缀: {model_id} -> {provider}")
                        break

            if not is_popular_provider:
                continue

            # 检查是否包含日期（排除带日期的旧版本）
            if date_pattern.search(model_id):
                print(f"⏭️ 跳过带日期的旧版本: {model_id}")
                continue

            # 检查是否包含排除关键词
            has_exclude_keyword = any(
                keyword in model_id or keyword in model_name
                for keyword in exclude_keywords
            )

            if has_exclude_keyword:
                print(f"⏭️ 跳过排除关键词: {model_id}")
                continue

            # 保留该模型
            print(f"✅ 保留模型: {model_id}")
            filtered.append(model)

        return filtered
