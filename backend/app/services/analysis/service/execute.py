from dataclasses import dataclass
from typing import Any

from .common import (
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
    RedisProgressTracker,
    datetime,
    get_postgres_db,
    get_provider_and_url_by_model,
    get_provider_by_model_name_sync,
    importlib,
    logger,
    uuid,
)


@dataclass(frozen=True)
class AnalysisThreadModelContext:
    quick_model: str
    deep_model: str
    llm_provider: str
    quick_model_config: dict[str, Any] | None = None
    deep_model_config: dict[str, Any] | None = None
    quick_provider_info: dict[str, Any] | None = None
    deep_provider_info: dict[str, Any] | None = None


def _model_config_from_doc(
    doc: dict[str, Any] | None, model_name: str
) -> dict[str, Any] | None:
    if not doc:
        return None
    llm_configs = doc.get("llm_configs")
    if not isinstance(llm_configs, list):
        return None
    for llm_config in llm_configs:
        if not isinstance(llm_config, dict):
            continue
        if llm_config.get("model_name") != model_name:
            continue
        return {
            "max_tokens": llm_config.get("max_tokens", 4000),
            "temperature": llm_config.get("temperature", 0.7),
            "timeout": llm_config.get("timeout", 180),
            "retry_times": llm_config.get("retry_times", 3),
            "api_base": llm_config.get("api_base"),
        }
    return None


def _system_settings_from_doc(doc: dict[str, Any] | None) -> dict[str, Any]:
    settings = doc.get("system_settings") if doc else {}
    return settings if isinstance(settings, dict) else {}


class AnalysisExecuteMixin:
    async def _load_active_system_config_doc_for_thread(
        self,
    ) -> dict[str, Any] | None:
        try:
            doc = await get_postgres_db().system_configs.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )
        except RuntimeError as exc:
            logger.warning("⚠️ 从 PostgreSQL 读取模型配置失败: %s，将使用默认参数", exc)
            return None
        return doc if isinstance(doc, dict) else None

    async def _resolve_thread_model_context(
        self, task: AnalysisTask
    ) -> AnalysisThreadModelContext:
        unified_config = getattr(
            importlib.import_module("app.core.unified"), "unified_config"
        )
        doc = await self._load_active_system_config_doc_for_thread()
        settings = _system_settings_from_doc(doc)
        default_model = doc.get("default_llm") if doc else None
        quick_model = (
            getattr(task.parameters, "quick_analysis_model", None)
            or settings.get("quick_analysis_model")
            or settings.get("quick_think_llm")
            or default_model
            or unified_config.get_quick_analysis_model()
        )
        deep_model = (
            getattr(task.parameters, "deep_analysis_model", None)
            or settings.get("deep_analysis_model")
            or settings.get("deep_think_llm")
            or default_model
            or unified_config.get_deep_analysis_model()
        )

        quick_provider_info = await get_provider_and_url_by_model(quick_model)
        deep_provider_info = await get_provider_and_url_by_model(deep_model)
        normalize_provider_key = getattr(
            importlib.import_module("trader.llm.clients.providers"),
            "normalize_provider_key",
        )
        return AnalysisThreadModelContext(
            quick_model=quick_model,
            deep_model=deep_model,
            llm_provider=normalize_provider_key(
                str(quick_provider_info.get("provider") or "qwen")
            ),
            quick_model_config=_model_config_from_doc(doc, quick_model),
            deep_model_config=_model_config_from_doc(doc, deep_model),
            quick_provider_info=quick_provider_info,
            deep_provider_info=deep_provider_info,
        )

    def _legacy_thread_model_context(
        self, task: AnalysisTask
    ) -> AnalysisThreadModelContext:
        unified_config = getattr(
            importlib.import_module("app.core.unified"), "unified_config"
        )
        quick_model = (
            getattr(task.parameters, "quick_analysis_model", None)
            or unified_config.get_quick_analysis_model()
        )
        deep_model = (
            getattr(task.parameters, "deep_analysis_model", None)
            or unified_config.get_deep_analysis_model()
        )
        normalize_provider_key = getattr(
            importlib.import_module("trader.llm.clients.providers"),
            "normalize_provider_key",
        )
        return AnalysisThreadModelContext(
            quick_model=quick_model,
            deep_model=deep_model,
            llm_provider=normalize_provider_key(
                get_provider_by_model_name_sync(quick_model)
            ),
        )

    def _execute_analysis_sync_with_progress(
        self,
        task: AnalysisTask,
        tracker: RedisProgressTracker,
        model_context: AnalysisThreadModelContext | None = None,
    ) -> AnalysisResult:
        """同步执行分析任务（在线程池中运行，带进度跟踪）"""
        try:
            # 在线程中重新初始化日志系统
            init_logging = getattr(
                importlib.import_module("trader.utils.logging.init"), "init_logging"
            )
            get_logger = getattr(
                importlib.import_module("trader.utils.logging.init"), "get_logger"
            )
            init_logging()
            thread_logger = get_logger("analysis_thread")

            thread_logger.info(
                f"🔄 [线程池] 开始执行分析任务: {task.task_id} - {task.symbol}"
            )
            logger.info(f"🔄 [线程池] 开始执行分析任务: {task.task_id} - {task.symbol}")

            # 环境检查
            tracker.update_progress("🔧 检查环境配置")

            # 使用标准配置函数创建完整配置
            model_context = model_context or self._legacy_thread_model_context(task)

            # 成本估算
            tracker.update_progress("💰 预估分析成本")

            # 参数配置
            tracker.update_progress("⚙️ 配置分析参数")

            # 使用标准配置函数创建完整配置
            create_analysis_config = getattr(
                importlib.import_module("app.services.analysis.simple"),
                "create_analysis_config",
            )
            config = create_analysis_config(
                research_depth=task.parameters.research_depth,
                selected_analysts=task.parameters.selected_analysts
                or ["market", "fundamentals"],
                quick_model=model_context.quick_model,
                deep_model=model_context.deep_model,
                llm_provider=model_context.llm_provider,
                market_type=getattr(task.parameters, "market_type", "A股"),
                quick_model_config=model_context.quick_model_config,
                deep_model_config=model_context.deep_model_config,
                quick_provider_info=model_context.quick_provider_info,
                deep_provider_info=model_context.deep_provider_info,
            )

            # 启动引擎
            tracker.update_progress("🚀 初始化AI分析引擎")

            # 获取分析引擎实例
            trading_graph = self._get_trading_graph(config)

            # 执行分析
            timezone = getattr(importlib.import_module("datetime"), "timezone")
            start_time = datetime.now(timezone.utc)
            analysis_date = task.parameters.analysis_date or datetime.now().strftime(
                "%Y-%m-%d"
            )

            # 创建进度回调函数
            def progress_callback(message: str):
                tracker.update_progress(message)

            # 调用现有的分析方法（同步调用，传递进度回调）
            _, decision = trading_graph.propagate(
                task.symbol, analysis_date, progress_callback
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            # 生成报告
            tracker.update_progress("📊 生成分析报告")

            # 从决策中提取模型信息
            model_info = (
                decision.get("model_info", "Unknown")
                if isinstance(decision, dict)
                else "Unknown"
            )

            # 构建结果
            result = AnalysisResult(
                analysis_id=str(uuid.uuid4()),
                summary=decision.get("summary", ""),
                recommendation=decision.get("recommendation", ""),
                confidence_score=decision.get("confidence_score", 0.0),
                risk_level=decision.get("risk_level", "中等"),
                key_points=decision.get("key_points", []),
                detailed_analysis=decision,
                execution_time=execution_time,
                tokens_used=decision.get("tokens_used", 0),
                model_info=model_info,  # 🔥 添加模型信息字段
            )

            logger.info(
                f"✅ [线程池] 分析任务完成: {task.task_id} - 耗时{execution_time:.2f}秒"
            )
            return result

        except Exception as e:
            logger.error(f"❌ [线程池] 执行分析任务失败: {task.task_id} - {e}")
            raise

    def _execute_analysis_sync(
        self,
        task: AnalysisTask,
        model_context: AnalysisThreadModelContext | None = None,
    ) -> AnalysisResult:
        """同步执行分析任务（在线程池中运行）"""
        try:
            logger.info(f"🔄 [线程池] 开始执行分析任务: {task.task_id} - {task.symbol}")

            model_context = model_context or self._legacy_thread_model_context(task)

            # 使用标准配置函数创建完整配置
            create_analysis_config = getattr(
                importlib.import_module("app.services.analysis.simple"),
                "create_analysis_config",
            )
            config = create_analysis_config(
                research_depth=task.parameters.research_depth,
                selected_analysts=task.parameters.selected_analysts
                or ["market", "fundamentals"],
                quick_model=model_context.quick_model,
                deep_model=model_context.deep_model,
                llm_provider=model_context.llm_provider,
                market_type=getattr(task.parameters, "market_type", "A股"),
                quick_model_config=model_context.quick_model_config,
                deep_model_config=model_context.deep_model_config,
                quick_provider_info=model_context.quick_provider_info,
                deep_provider_info=model_context.deep_provider_info,
            )

            # 获取分析引擎实例
            trading_graph = self._get_trading_graph(config)

            # 执行分析
            timezone = getattr(importlib.import_module("datetime"), "timezone")
            start_time = datetime.now(timezone.utc)
            analysis_date = task.parameters.analysis_date or datetime.now().strftime(
                "%Y-%m-%d"
            )

            # 调用现有的分析方法（同步调用）
            _, decision = trading_graph.propagate(task.symbol, analysis_date)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            # 从决策中提取模型信息
            model_info = (
                decision.get("model_info", "Unknown")
                if isinstance(decision, dict)
                else "Unknown"
            )

            # 构建结果
            result = AnalysisResult(
                analysis_id=str(uuid.uuid4()),
                summary=decision.get("summary", ""),
                recommendation=decision.get("recommendation", ""),
                confidence_score=decision.get("confidence_score", 0.0),
                risk_level=decision.get("risk_level", "中等"),
                key_points=decision.get("key_points", []),
                detailed_analysis=decision,
                execution_time=execution_time,
                tokens_used=decision.get("tokens_used", 0),
                model_info=model_info,  # 🔥 添加模型信息字段
            )

            logger.info(
                f"✅ [线程池] 分析任务完成: {task.task_id} - 耗时{execution_time:.2f}秒"
            )
            return result

        except Exception as e:
            logger.error(f"❌ [线程池] 执行分析任务失败: {task.task_id} - {e}")
            raise

    async def _execute_single_analysis_async(self, task: AnalysisTask):
        """异步执行个股分析任务（在后台运行，不阻塞主线程）"""
        tracker = None
        try:
            logger.info(f"🔄 开始执行分析任务: {task.task_id} - {task.symbol}")

            # 创建进度跟踪器
            tracker = RedisProgressTracker(
                task_id=task.task_id,
                analysts=task.parameters.selected_analysts
                or ["market", "fundamentals"],
                research_depth=task.parameters.research_depth or "标准",
                llm_provider="dashscope",
            )

            # 缓存进度跟踪器
            self._trackers[task.task_id] = tracker

            # 初始化进度
            tracker.update_progress("🚀 开始股票分析")
            await self._update_task_status_with_tracker(
                task.task_id, AnalysisStatus.PROCESSING, tracker
            )

            model_context = await self._resolve_thread_model_context(task)

            # 在线程池中执行分析，避免阻塞事件循环
            asyncio = importlib.import_module("asyncio")
            importlib.import_module("concurrent.futures")
            concurrent = importlib.import_module("concurrent")

            loop = asyncio.get_event_loop()

            # 使用线程池执行器运行同步的分析代码
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    self._execute_analysis_sync_with_progress,
                    task,
                    tracker,
                    model_context,
                )

            # 标记完成
            tracker.mark_completed()
            await self._update_task_status_with_tracker(
                task.task_id, AnalysisStatus.COMPLETED, tracker, result
            )

            # 记录 token 使用
            try:
                # 记录使用情况
                await self._record_token_usage(
                    task, result, model_context.llm_provider, model_context.deep_model
                )
            except Exception as e:
                logger.error(f"⚠️  记录 token 使用失败: {e}")

            logger.info(f"✅ 分析任务完成: {task.task_id}")

        except Exception as e:
            logger.error(f"❌ 分析任务失败: {task.task_id} - {e}")

            # 标记失败
            if tracker:
                tracker.mark_failed(str(e))
                await self._update_task_status_with_tracker(
                    task.task_id, AnalysisStatus.FAILED, tracker
                )
            else:
                await self._update_task_status(
                    task.task_id,
                    AnalysisStatus.FAILED,
                    0,
                    AnalysisResult(error_message=str(e)),
                )
        finally:
            # 清理进度跟踪器缓存
            if task.task_id in self._trackers:
                del self._trackers[task.task_id]
