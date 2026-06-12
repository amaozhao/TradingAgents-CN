from .common import Any, POSTGRES_AVAILABLE, Path, PostgresStorage, logger, re
from app.core.config import settings as app_settings


class ConfigManagerBaseMixin:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

        self.models_file = self.config_dir / "models.json"
        self.pricing_file = self.config_dir / "pricing.json"
        self.usage_file = self.config_dir / "usage.json"
        self.settings_file = self.config_dir / "settings.json"

        # Settings 在 app.core.config 中统一加载 backend/.env
        self._load_env_file()

        # 初始化PostgreSQL token 存储（如果可用）
        self.postgres_storage = None
        self._init_postgres_storage()

        self._init_default_configs()

    def _load_env_file(self):
        """记录 Settings 配置文件状态。"""
        backend_root = Path(__file__).resolve().parents[3]
        env_file = backend_root / ".env"

        if env_file.exists():
            logger.info(f"🔍 [ConfigManager] 使用 Settings 配置文件: {env_file}")
            logger.info(
                f"🔍 [ConfigManager] DASHSCOPE_API_KEY: {'有值' if app_settings.DASHSCOPE_API_KEY else '空'}"
            )

    def _get_env_api_key(self, provider: str) -> str:
        """从环境变量获取API密钥"""
        env_key_map = {
            "dashscope": "DASHSCOPE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        env_key = env_key_map.get(provider.lower())
        if env_key:
            api_key = app_settings.text_value(env_key)
            # 对OpenAI密钥进行格式验证（始终启用）
            if provider.lower() == "openai" and api_key:
                if not self.validate_openai_api_key_format(api_key):
                    logger.warning(
                        f"⚠️ OpenAI API密钥格式不正确，将被忽略: {api_key[:10]}..."
                    )
                    return ""
            return api_key
        return ""

    def validate_openai_api_key_format(self, api_key: str) -> bool:
        """
        验证OpenAI API密钥格式

        OpenAI API密钥格式规则：
        1. 以 'sk-' 开头
        2. 总长度通常为51个字符
        3. 包含字母、数字和可能的特殊字符

        Args:
            api_key: 要验证的API密钥

        Returns:
            bool: 格式是否正确
        """
        if not api_key or not isinstance(api_key, str):
            return False

        # 检查是否以 'sk-' 开头
        if not api_key.startswith("sk-"):
            return False

        # 检查长度（OpenAI密钥通常为51个字符）
        if len(api_key) != 51:
            return False

        # 检查格式：sk- 后面应该是48个字符的字母数字组合
        pattern = r"^sk-[A-Za-z0-9]{48}$"
        if not re.match(pattern, api_key):
            return False

        return True

    def _init_postgres_storage(self):
        """初始化PostgreSQL token 存储"""
        logger.info("🔧 [ConfigManager] 开始初始化 PostgreSQL token 存储...")
        self.close_postgres_storage()

        if not POSTGRES_AVAILABLE:
            logger.warning(
                "⚠️ [ConfigManager] PostgreSQL token 存储不可用，将使用 JSON 文件存储"
            )
            return

        # 检查是否启用 PostgreSQL token 存储。
        use_postgres = app_settings.USE_POSTGRES_STORAGE
        use_postgres_env = str(use_postgres).lower()

        logger.info(
            f"🔍 [ConfigManager] USE_POSTGRES_STORAGE={use_postgres_env} (解析为: {use_postgres})"
        )

        if not use_postgres:
            logger.info(
                "ℹ️ [ConfigManager] PostgreSQL token 存储未启用，将使用 JSON 文件存储"
            )
            return

        try:
            database_name = app_settings.POSTGRES_DB

            logger.info(f"🔍 [ConfigManager] POSTGRES_DB={database_name}")

            logger.info("🔄 [ConfigManager] 正在创建 PostgreSQL token 存储实例...")
            storage_cls: Any = PostgresStorage
            self.postgres_storage = storage_cls(database_name=database_name)

            if self.postgres_storage.is_connected():
                logger.info(
                    f"✅ [ConfigManager] PostgreSQL token 存储已启用: {database_name}.token_usage"
                )
            else:
                self.postgres_storage = None
                logger.warning(
                    "⚠️ [ConfigManager] PostgreSQL token 存储连接失败，将使用JSON文件存储"
                )

        except Exception as e:
            logger.error(
                f"❌ [ConfigManager] PostgreSQL token 存储初始化失败: {e}",
                exc_info=True,
            )
            self.postgres_storage = None

    def close_postgres_storage(self) -> None:
        """关闭PostgreSQL token 存储连接"""
        storage = getattr(self, "postgres_storage", None)
        if storage is None:
            return

        close = getattr(storage, "close", None)
        if close is not None:
            close()
        self.postgres_storage = None
