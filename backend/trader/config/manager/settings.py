# ruff: noqa: F403,F405
from .common import *


class ConfigManagerSettingsMixin:
    def load_settings(self) -> Dict[str, Any]:
        """加载设置，合并.env中的配置"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                # 如果设置文件不存在，创建默认设置
                settings = {
                    "default_provider": "dashscope",
                    "default_model": "qwen-turbo",
                    "enable_cost_tracking": True,
                    "cost_alert_threshold": 100.0,
                    "currency_preference": "CNY",
                    "auto_save_usage": True,
                    "max_usage_records": 10000,
                    "data_dir": os.path.join(
                        os.path.expanduser("~"), "Documents", "TradingAgents", "data"
                    ),
                    "cache_dir": os.path.join(
                        os.path.expanduser("~"),
                        "Documents",
                        "TradingAgents",
                        "data",
                        "cache",
                    ),
                    "results_dir": os.path.join(
                        os.path.expanduser("~"), "Documents", "TradingAgents", "results"
                    ),
                    "auto_create_dirs": True,
                    "openai_enabled": False,
                }
                self.save_settings(settings)
        except Exception as e:
            logger.error(f"加载设置失败: {e}")
            settings = {}

        # 合并.env中的其他配置
        env_settings: Dict[str, Any] = {
            "finnhub_api_key": os.getenv("FINNHUB_API_KEY", ""),
            "reddit_client_id": os.getenv("REDDIT_CLIENT_ID", ""),
            "reddit_client_secret": os.getenv("REDDIT_CLIENT_SECRET", ""),
            "reddit_user_agent": os.getenv("REDDIT_USER_AGENT", ""),
            "results_dir": os.getenv("TRADING_AGENTS_RESULTS_DIR", ""),
            "log_level": os.getenv("TRADING_AGENTS_LOG_LEVEL", "INFO"),
            "data_dir": os.getenv("TRADING_AGENTS_DATA_DIR", ""),  # 数据目录环境变量
            "cache_dir": os.getenv("TRADING_AGENTS_CACHE_DIR", ""),  # 缓存目录环境变量
        }

        # 添加OpenAI相关配置
        openai_enabled_env = os.getenv("OPENAI_ENABLED", "").lower()
        if openai_enabled_env in ["true", "false"]:
            env_settings["openai_enabled"] = openai_enabled_env == "true"

        # 只有当环境变量存在且不为空时才覆盖
        for key, value in env_settings.items():
            # 对于布尔值，直接使用
            if isinstance(value, bool):
                settings[key] = value
            # 对于字符串，只有非空时才覆盖
            elif value != "" and value is not None:
                settings[key] = value

        return settings

    def get_env_config_status(self) -> Dict[str, Any]:
        """获取.env配置状态"""
        return {
            "env_file_exists": (Path(__file__).resolve().parents[3] / ".env").exists(),
            "api_keys": {
                "dashscope": bool(os.getenv("DASHSCOPE_API_KEY")),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "google": bool(os.getenv("GOOGLE_API_KEY")),
                "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
                "finnhub": bool(os.getenv("FINNHUB_API_KEY")),
            },
            "other_configs": {
                "reddit_configured": bool(
                    os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")
                ),
                "results_dir": os.getenv("TRADING_AGENTS_RESULTS_DIR", "./results"),
                "log_level": os.getenv("TRADING_AGENTS_LOG_LEVEL", "INFO"),
            },
        }

    def save_settings(self, settings: Dict[str, Any]):
        """保存设置"""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存设置失败: {e}")

    def get_enabled_models(self) -> List[ModelConfig]:
        """获取启用的模型"""
        models = self.load_models()
        return [model for model in models if model.enabled and model.api_key]

    def get_model_by_name(
        self, provider: str, model_name: str
    ) -> Optional[ModelConfig]:
        """根据名称获取模型配置"""
        models = self.load_models()
        for model in models:
            if model.provider == provider and model.model_name == model_name:
                return model
        return None

    def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取使用统计"""
        # 优先使用 PostgreSQL 获取统计
        if self.postgres_storage and self.postgres_storage.is_connected():
            try:
                # 从PostgreSQL document store获取基础统计
                stats = self.postgres_storage.get_usage_statistics(days)
                # 获取供应商统计
                provider_stats = self.postgres_storage.get_provider_statistics(days)

                if stats:
                    stats["provider_stats"] = provider_stats
                    stats["records_count"] = stats.get("total_requests", 0)
                    return stats
            except Exception as e:
                logger.error(f"⚠️ PostgreSQL统计获取失败，回退到JSON文件: {e}")

        # 回退到JSON文件统计
        records = self.load_usage_records()

        # 过滤最近N天的记录
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        tz = ZoneInfo(get_timezone_name())
        cutoff_date = datetime.now(tz) - timedelta(days=days)

        recent_records = []
        for record in records:
            try:
                record_date = datetime.fromisoformat(
                    record.timestamp.replace("Z", "+00:00")
                )
                if record_date.tzinfo is None:
                    record_date = record_date.replace(tzinfo=tz)
                if record_date >= cutoff_date:
                    recent_records.append(record)
            except Exception:
                continue

        # 统计数据
        total_cost = sum(record.cost for record in recent_records)
        total_input_tokens = sum(record.input_tokens for record in recent_records)
        total_output_tokens = sum(record.output_tokens for record in recent_records)

        # 按供应商统计
        provider_stats = {}
        for record in recent_records:
            if record.provider not in provider_stats:
                provider_stats[record.provider] = {
                    "cost": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "requests": 0,
                }
            provider_stats[record.provider]["cost"] += record.cost
            provider_stats[record.provider]["input_tokens"] += record.input_tokens
            provider_stats[record.provider]["output_tokens"] += record.output_tokens
            provider_stats[record.provider]["requests"] += 1

        return {
            "period_days": days,
            "total_cost": round(total_cost, 4),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_requests": len(recent_records),
            "provider_stats": provider_stats,
            "records_count": len(recent_records),
        }

    def get_data_dir(self) -> str:
        """获取数据目录路径"""
        settings = self.load_settings()
        data_dir = settings.get("data_dir")
        if not data_dir:
            # 如果没有配置，使用默认路径
            data_dir = os.path.join(
                os.path.expanduser("~"), "Documents", "TradingAgents", "data"
            )
        return data_dir

    def set_data_dir(self, data_dir: str):
        """设置数据目录路径"""
        settings = self.load_settings()
        settings["data_dir"] = data_dir
        # 同时更新缓存目录
        settings["cache_dir"] = os.path.join(data_dir, "cache")
        self.save_settings(settings)

        # 如果启用自动创建目录，则创建目录
        if settings.get("auto_create_dirs", True):
            self.ensure_directories_exist()

    def ensure_directories_exist(self):
        """确保必要的目录存在"""
        settings = self.load_settings()

        directories = [
            settings.get("data_dir"),
            settings.get("cache_dir"),
            settings.get("results_dir"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data"),
            os.path.join(settings.get("data_dir", ""), "finnhub_data", "news_data"),
            os.path.join(
                settings.get("data_dir", ""), "finnhub_data", "insider_sentiment"
            ),
            os.path.join(
                settings.get("data_dir", ""), "finnhub_data", "insider_transactions"
            ),
        ]

        for directory in directories:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"✅ 创建目录: {directory}")
                except Exception as e:
                    logger.error(f"❌ 创建目录失败 {directory}: {e}")

    def set_openai_enabled(self, enabled: bool):
        """设置OpenAI模型启用状态"""
        settings = self.load_settings()
        settings["openai_enabled"] = enabled
        self.save_settings(settings)
        logger.info(f"🔧 OpenAI模型启用状态已设置为: {enabled}")

    def is_openai_enabled(self) -> bool:
        """检查OpenAI模型是否启用"""
        settings = self.load_settings()
        return settings.get("openai_enabled", False)

    def get_openai_config_status(self) -> Dict[str, Any]:
        """获取OpenAI配置状态"""
        openai_key = os.getenv("OPENAI_API_KEY", "")
        key_valid = (
            self.validate_openai_api_key_format(openai_key) if openai_key else False
        )

        return {
            "api_key_present": bool(openai_key),
            "api_key_valid_format": key_valid,
            "enabled": self.is_openai_enabled(),
            "models_available": self.is_openai_enabled() and key_valid,
            "api_key_preview": f"{openai_key[:10]}..." if openai_key else "未配置",
        }
