from .common import (
    Any,
    Dict,
    dual_write_hot_document,
    get_postgres_db,
    logger,
    normalize_provider_key,
    now_tz,
)


class BaseConfigMixin:
    def __init__(self, db_manager=None):
        self.db = None
        self.db_manager = db_manager

    async def _dual_write_config_document(
        self, collection: str, document: Dict[str, Any]
    ) -> None:
        result = await dual_write_hot_document(collection, document)
        if result.status == "failed":
            logger.warning(
                "⚠️ 配置 PostgreSQL 双写失败: collection=%s reason=%s",
                collection,
                result.reason,
            )

    async def _dual_write_config_tombstone(
        self, collection: str, document: Dict[str, Any]
    ) -> None:
        await self._dual_write_config_document(
            collection,
            {
                **document,
                "enabled": False,
                "deleted": True,
                "deleted_at": now_tz(),
            },
        )

    async def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            if self.db_manager and self.db_manager.postgres_db is not None:
                # 如果有DatabaseManager实例，直接使用
                self.db = self.db_manager.postgres_db
            else:
                # 否则使用全局函数
                self.db = get_postgres_db()
        return self.db

    @staticmethod
    def _provider_to_string(provider: Any) -> str:
        """统一提取 provider 字符串，兼容历史枚举对象和普通字符串。"""
        if provider is None:
            return ""

        if hasattr(provider, "value"):
            provider = provider.value

        return str(provider).strip()

    @classmethod
    def _providers_match(cls, left: Any, right: Any) -> bool:
        """兼容历史数据形态比较 provider。"""
        left_provider = cls._provider_to_string(left).lower()
        right_provider = cls._provider_to_string(right).lower()

        if left_provider == right_provider:
            return True

        if not left_provider or not right_provider:
            return False

        return normalize_provider_key(left_provider) == normalize_provider_key(
            right_provider
        )
