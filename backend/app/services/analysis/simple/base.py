from .common import (
    Any,
    Dict,
    DocumentId,
    List,
    Optional,
    PyDocumentId,
    RedisProgressTracker,
    TaskStatus,
    cast,
    dual_write_hot_document,
    get_memory_state_manager,
    importlib,
    logger,
    settings,
)
from .provider import _ensure_trading_agents_logging, _get_stock_info_safe


class BaseAnalysisMixin:
    def __init__(self):
        self._trading_graph_cache = {}
        self.memory_manager = get_memory_state_manager()

        # 进度跟踪器缓存
        self._trackers: Dict[str, RedisProgressTracker] = {}

        # 🔧 创建共享的线程池，支持并发执行多个分析任务
        max_workers = max(1, int(settings.ANALYSIS_MAX_WORKERS))
        importlib.import_module("concurrent.futures")
        concurrent = importlib.import_module("concurrent")
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        )

        logger.info(f"🔧 [服务初始化] SimpleAnalysisService 实例ID: {id(self)}")
        logger.info(f"🔧 [服务初始化] 内存管理器实例ID: {id(self.memory_manager)}")
        logger.info(f"🔧 [服务初始化] 线程池最大并发数: {max_workers}")

        # 设置 WebSocket 管理器
        # 简单的股票名称缓存，减少重复查询
        self._stock_name_cache: Dict[str, str] = {}

        # 设置 WebSocket 管理器
        try:
            get_websocket_manager = getattr(
                importlib.import_module("app.services.socket"), "get_websocket_manager"
            )
            self.memory_manager.set_websocket_manager(get_websocket_manager())
        except ImportError:
            logger.warning("⚠️ WebSocket 管理器不可用")

    async def _update_progress_async(
        self,
        task_id: str,
        progress: int,
        message: str,
        current_step: str | None = None,
    ):
        """异步更新进度（内存和PostgreSQL）"""
        try:
            # 更新内存
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=progress,
                message=message,
                current_step=current_step or message,
            )

            # 更新 PostgreSQL
            get_postgres_db = getattr(
                importlib.import_module("app.core.database"), "get_postgres_db"
            )
            datetime = getattr(importlib.import_module("datetime"), "datetime")
            db = get_postgres_db()
            update_data = {
                "progress": progress,
                "current_step": current_step or message,
                "message": message,
                "updated_at": datetime.utcnow(),
            }
            await db.analysis_tasks.update_one(
                {"task_id": task_id}, {"$set": update_data}
            )
            await dual_write_hot_document(
                "analysis_tasks", {"task_id": task_id, **update_data}
            )
            logger.debug(f"✅ [异步更新] 已更新内存和PostgreSQL: {progress}%")
        except Exception as e:
            logger.warning(f"⚠️ [异步更新] 失败: {e}")

    def _resolve_stock_name(self, code: Optional[str]) -> str:
        """解析股票名称（带缓存）"""
        if not code:
            return ""
        # 命中缓存
        if code in self._stock_name_cache:
            return self._stock_name_cache[code]
        name = None
        try:
            if _get_stock_info_safe:
                info = _get_stock_info_safe(code)
                if isinstance(info, dict):
                    name = info.get("name")
        except Exception as e:
            logger.warning(f"⚠️ 获取股票名称失败: {code} - {e}")
        if not name:
            name = f"股票{code}"
        # 写缓存
        self._stock_name_cache[code] = name
        return name

    def _enrich_stock_names(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为任务列表补齐股票名称(就地更新)"""
        try:
            for t in tasks:
                code = t.get("stock_code") or t.get("stock_symbol")
                name = t.get("stock_name")
                if not name and code:
                    t["stock_name"] = self._resolve_stock_name(code)
        except Exception as e:
            logger.warning(f"⚠️ 补齐股票名称时出现异常: {e}")
        return tasks

    def _convert_user_id(self, user_id: str) -> PyDocumentId:
        """将字符串用户ID转换为PyDocumentId"""
        try:
            logger.info(f"🔄 开始转换用户ID: {user_id} (类型: {type(user_id)})")

            # 如果是admin用户，使用固定的DocumentId
            if user_id == "admin":
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
        """获取或创建分析引擎实例

        ⚠️ 注意：为了避免并发执行时的数据混淆，每次都创建新实例
        虽然这会增加一些初始化开销，但可以确保线程安全

        TradingAgentsGraph 实例包含可变状态（self.ticker, self.curr_state等），
        如果多个线程共享同一个实例，会导致数据混淆。
        """
        # 🔧 [并发安全] 每次都创建新实例，避免多线程共享状态
        # 不再使用缓存，因为 TradingAgentsGraph 有可变的实例变量
        logger.info("🔧 创建新的分析引擎实例（并发安全模式）...")
        _ensure_trading_agents_logging()
        TradingAgentsGraph = getattr(
            importlib.import_module("trader.graph.trading"), "TradingAgentsGraph"
        )

        trading_graph = TradingAgentsGraph(
            selected_analysts=config.get(
                "selected_analysts", ["market", "fundamentals"]
            ),
            debug=config.get("debug", False),
            config=config,
        )

        logger.info(f"✅ 分析引擎实例创建成功（实例ID: {id(trading_graph)}）")

        return trading_graph
