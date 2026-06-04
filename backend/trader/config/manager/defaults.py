# ruff: noqa: F403,F405
from .common import *


class ConfigManagerDefaultsMixin:
    def _init_default_configs(self):
        """初始化默认配置"""
        # 默认模型配置
        if not self.models_file.exists():
            default_models = [
                ModelConfig(
                    provider="dashscope",
                    model_name="qwen-turbo",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7,
                ),
                ModelConfig(
                    provider="dashscope",
                    model_name="qwen-plus-latest",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7,
                ),
                ModelConfig(
                    provider="openai",
                    model_name="gpt-3.5-turbo",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False,
                ),
                ModelConfig(
                    provider="openai",
                    model_name="gpt-4",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7,
                    enabled=False,
                ),
                ModelConfig(
                    provider="google",
                    model_name="gemini-2.5-pro",
                    api_key="",
                    max_tokens=4000,
                    temperature=0.7,
                    enabled=False,
                ),
                ModelConfig(
                    provider="deepseek",
                    model_name="deepseek-chat",
                    api_key="",
                    max_tokens=8000,
                    temperature=0.7,
                    enabled=False,
                ),
            ]
            self.save_models(default_models)

        # 默认定价配置
        if not self.pricing_file.exists():
            default_pricing = [
                # 阿里百炼定价 (人民币)
                PricingConfig("dashscope", "qwen-turbo", 0.002, 0.006, "CNY"),
                PricingConfig("dashscope", "qwen-plus-latest", 0.004, 0.012, "CNY"),
                PricingConfig("dashscope", "qwen-max", 0.02, 0.06, "CNY"),
                # DeepSeek定价 (人民币) - 2025年最新价格
                PricingConfig("deepseek", "deepseek-chat", 0.0014, 0.0028, "CNY"),
                PricingConfig("deepseek", "deepseek-coder", 0.0014, 0.0028, "CNY"),
                # OpenAI定价 (美元)
                PricingConfig("openai", "gpt-3.5-turbo", 0.0015, 0.002, "USD"),
                PricingConfig("openai", "gpt-4", 0.03, 0.06, "USD"),
                PricingConfig("openai", "gpt-4-turbo", 0.01, 0.03, "USD"),
                # Google定价 (美元)
                PricingConfig("google", "gemini-2.5-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-2.5-flash", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-2.0-flash", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-1.5-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-1.5-flash", 0.00025, 0.0005, "USD"),
                PricingConfig(
                    "google",
                    "gemini-2.5-flash-lite-preview-06-17",
                    0.00025,
                    0.0005,
                    "USD",
                ),
                PricingConfig("google", "gemini-pro", 0.00025, 0.0005, "USD"),
                PricingConfig("google", "gemini-pro-vision", 0.00025, 0.0005, "USD"),
            ]
            self.save_pricing(default_pricing)

        # 默认设置
        if not self.settings_file.exists():
            # 导入默认数据目录配置
            os = importlib.import_module("os")
            default_data_dir = os.path.join(
                os.path.expanduser("~"), "Documents", "TradingAgents", "data"
            )

            default_settings = {
                "default_provider": "dashscope",
                "default_model": "qwen-turbo",
                "enable_cost_tracking": True,
                "cost_alert_threshold": 100.0,  # 成本警告阈值
                "currency_preference": "CNY",
                "auto_save_usage": True,
                "max_usage_records": 10000,
                "data_dir": default_data_dir,  # 数据目录配置
                "cache_dir": os.path.join(default_data_dir, "cache"),  # 缓存目录
                "results_dir": os.path.join(
                    os.path.expanduser("~"), "Documents", "TradingAgents", "results"
                ),  # 结果目录
                "auto_create_dirs": True,  # 自动创建目录
                "openai_enabled": False,  # OpenAI模型是否启用
            }
            self.save_settings(default_settings)

    def load_models(self) -> List[ModelConfig]:
        """加载模型配置，优先使用.env中的API密钥"""
        try:
            with open(self.models_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                models = [ModelConfig(**item) for item in data]

                # 获取设置
                settings = self.load_settings()
                openai_enabled = settings.get("openai_enabled", False)

                # 合并.env中的API密钥（优先级更高）
                for model in models:
                    env_api_key = self._get_env_api_key(model.provider)
                    if env_api_key:
                        model.api_key = env_api_key
                        # 如果.env中有API密钥，自动启用该模型
                        if not model.enabled:
                            model.enabled = True

                    # 特殊处理OpenAI模型
                    if model.provider.lower() == "openai":
                        # 检查OpenAI是否在配置中启用
                        if not openai_enabled:
                            model.enabled = False
                            logger.info(f"🔒 OpenAI模型已禁用: {model.model_name}")
                        # 如果有API密钥但格式不正确，禁用模型（验证始终启用）
                        elif model.api_key and not self.validate_openai_api_key_format(
                            model.api_key
                        ):
                            model.enabled = False
                            logger.warning(
                                f"⚠️ OpenAI模型因密钥格式不正确而禁用: {model.model_name}"
                            )

                return models
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")
            return []

    def save_models(self, models: List[ModelConfig]):
        """保存模型配置"""
        try:
            data = [asdict(model) for model in models]
            with open(self.models_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模型配置失败: {e}")

    def load_pricing(self) -> List[PricingConfig]:
        """加载定价配置"""
        try:
            with open(self.pricing_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [PricingConfig(**item) for item in data]
        except Exception as e:
            logger.error(f"加载定价配置失败: {e}")
            return []

    def save_pricing(self, pricing: List[PricingConfig]):
        """保存定价配置"""
        try:
            data = [asdict(price) for price in pricing]
            with open(self.pricing_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存定价配置失败: {e}")

    def load_usage_records(self) -> List[UsageRecord]:
        """加载使用记录"""
        try:
            if not self.usage_file.exists():
                return []
            with open(self.usage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [UsageRecord(**item) for item in data]
        except Exception as e:
            logger.error(f"加载使用记录失败: {e}")
            return []

    def save_usage_records(self, records: List[UsageRecord]):
        """保存使用记录"""
        try:
            data = [asdict(record) for record in records]
            with open(self.usage_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存使用记录失败: {e}")
