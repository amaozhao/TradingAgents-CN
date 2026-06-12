from .common import (
    Any,
    Dict,
    DocumentId,
    PyDocumentId,
    QueueService,
    RedisProgressTracker,
    UsageStatisticsService,
    cast,
    get_redis_client,
    importlib,
    json,
    logger,
)
from .common import _ensure_trading_agents_logging


class AnalysisBaseMixin:
    def __init__(self):
        # 获取Redis客户端
        redis_client = get_redis_client()
        self.queue_service = QueueService(redis_client)
        # 初始化使用统计服务
        self.usage_service = UsageStatisticsService()
        self._trading_graph_cache = {}
        # 进度跟踪器缓存
        self._trackers: Dict[str, RedisProgressTracker] = {}

    def _convert_user_id(self, user_id: str) -> PyDocumentId:
        """将字符串用户ID转换为PyDocumentId"""
        try:
            logger.info(f"🔄 开始转换用户ID: {user_id} (类型: {type(user_id)})")

            # 如果是admin用户，使用固定的DocumentId
            if user_id == "admin":
                # 使用固定的DocumentId作为admin用户ID
                admin_document_id = DocumentId("507f1f77bcf86cd799439011")
                logger.info(f"🔄 转换admin用户ID: {user_id} -> {admin_document_id}")
                return cast(PyDocumentId, admin_document_id)
            else:
                # 尝试将字符串转换为DocumentId
                document_id = DocumentId(user_id)
                logger.info(f"🔄 转换用户ID: {user_id} -> {document_id}")
                return cast(PyDocumentId, document_id)
        except Exception as e:
            logger.error(f"❌ 用户ID转换失败: {user_id} -> {e}")
            # 如果转换失败，生成一个新的DocumentId
            new_document_id = DocumentId()
            logger.warning(f"⚠️ 生成新的用户ID: {new_document_id}")
            return cast(PyDocumentId, new_document_id)

    def _get_trading_graph(self, config: Dict[str, Any]) -> Any:
        """获取或创建分析引擎图实例（带缓存）- 与个股分析保持一致"""
        config_key = json.dumps(config, sort_keys=True)

        if config_key not in self._trading_graph_cache:
            _ensure_trading_agents_logging()
            TradingAgentsGraph = getattr(
                importlib.import_module("trader.graph.trading"), "TradingAgentsGraph"
            )

            # 直接使用完整配置，不再合并DEFAULT_CONFIG（因为create_analysis_config已经处理了）
            # 这与个股分析服务和web目录的方式一致
            self._trading_graph_cache[config_key] = TradingAgentsGraph(
                selected_analysts=config.get(
                    "selected_analysts", ["market", "fundamentals"]
                ),
                debug=config.get("debug", False),
                config=config,
            )

            logger.info(
                f"创建新的分析引擎实例: {config.get('llm_provider', 'default')}"
            )

        return self._trading_graph_cache[config_key]
