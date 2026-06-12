from .common import (
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
    RedisProgressTracker,
    datetime,
    get_provider_by_model_name_sync,
    importlib,
    logger,
    uuid,
)


class AnalysisExecuteMixin:
    def _execute_analysis_sync_with_progress(
        self, task: AnalysisTask, tracker: RedisProgressTracker
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

            # 🔧 从 PostgreSQL 数据库读取模型的完整配置参数（而不是从 JSON 文件）
            quick_model_config = None
            deep_model_config = None

            try:
                get_postgres_db_sync = getattr(
                    importlib.import_module("app.core.database"), "get_postgres_db_sync"
                )
                db = get_postgres_db_sync()
                collection = db.system_configs

                # 查询最新的活跃配置
                doc = collection.find_one({"is_active": True}, sort=[("version", -1)])

                if doc and "llm_configs" in doc:
                    llm_configs = doc["llm_configs"]
                    logger.info(
                        f"✅ 从 PostgreSQL 读取到 {len(llm_configs)} 个模型配置"
                    )

                    for llm_config in llm_configs:
                        if llm_config.get("model_name") == quick_model:
                            quick_model_config = {
                                "max_tokens": llm_config.get("max_tokens", 4000),
                                "temperature": llm_config.get("temperature", 0.7),
                                "timeout": llm_config.get("timeout", 180),
                                "retry_times": llm_config.get("retry_times", 3),
                                "api_base": llm_config.get("api_base"),
                            }
                            logger.info(f"✅ 读取快速模型配置: {quick_model}")
                            logger.info(
                                f"   max_tokens={quick_model_config['max_tokens']}, temperature={quick_model_config['temperature']}"
                            )
                            logger.info(
                                f"   timeout={quick_model_config['timeout']}, retry_times={quick_model_config['retry_times']}"
                            )
                            logger.info(f"   api_base={quick_model_config['api_base']}")

                        if llm_config.get("model_name") == deep_model:
                            deep_model_config = {
                                "max_tokens": llm_config.get("max_tokens", 4000),
                                "temperature": llm_config.get("temperature", 0.7),
                                "timeout": llm_config.get("timeout", 180),
                                "retry_times": llm_config.get("retry_times", 3),
                                "api_base": llm_config.get("api_base"),
                            }
                            logger.info(
                                f"✅ 读取深度模型配置: {deep_model} - {deep_model_config}"
                            )
                else:
                    logger.warning("⚠️ PostgreSQL 中没有找到系统配置，将使用默认参数")
            except Exception as e:
                logger.warning(f"⚠️ 从 PostgreSQL 读取模型配置失败: {e}，将使用默认参数")

            # 成本估算
            tracker.update_progress("💰 预估分析成本")

            # 根据模型名称动态查找供应商（同步版本）
            normalize_provider_key = getattr(
                importlib.import_module("trader.llm.clients.providers"),
                "normalize_provider_key",
            )

            llm_provider = normalize_provider_key(
                get_provider_by_model_name_sync(quick_model)
            )

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
                quick_model=quick_model,
                deep_model=deep_model,
                llm_provider=llm_provider,
                market_type=getattr(task.parameters, "market_type", "A股"),
                quick_model_config=quick_model_config,  # 传递模型配置
                deep_model_config=deep_model_config,  # 传递模型配置
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

    def _execute_analysis_sync(self, task: AnalysisTask) -> AnalysisResult:
        """同步执行分析任务（在线程池中运行）"""
        try:
            logger.info(f"🔄 [线程池] 开始执行分析任务: {task.task_id} - {task.symbol}")

            # 使用标准配置函数创建完整配置
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

            # 🔧 从 PostgreSQL 数据库读取模型的完整配置参数（而不是从 JSON 文件）
            quick_model_config = None
            deep_model_config = None

            try:
                get_postgres_db_sync = getattr(
                    importlib.import_module("app.core.database"), "get_postgres_db_sync"
                )
                db = get_postgres_db_sync()
                collection = db.system_configs

                # 查询最新的活跃配置
                doc = collection.find_one({"is_active": True}, sort=[("version", -1)])

                if doc and "llm_configs" in doc:
                    llm_configs = doc["llm_configs"]
                    logger.info(
                        f"✅ 从 PostgreSQL 读取到 {len(llm_configs)} 个模型配置"
                    )

                    for llm_config in llm_configs:
                        if llm_config.get("model_name") == quick_model:
                            quick_model_config = {
                                "max_tokens": llm_config.get("max_tokens", 4000),
                                "temperature": llm_config.get("temperature", 0.7),
                                "timeout": llm_config.get("timeout", 180),
                                "retry_times": llm_config.get("retry_times", 3),
                                "api_base": llm_config.get("api_base"),
                            }
                            logger.info(f"✅ 读取快速模型配置: {quick_model}")
                            logger.info(
                                f"   max_tokens={quick_model_config['max_tokens']}, temperature={quick_model_config['temperature']}"
                            )
                            logger.info(
                                f"   timeout={quick_model_config['timeout']}, retry_times={quick_model_config['retry_times']}"
                            )
                            logger.info(f"   api_base={quick_model_config['api_base']}")

                        if llm_config.get("model_name") == deep_model:
                            deep_model_config = {
                                "max_tokens": llm_config.get("max_tokens", 4000),
                                "temperature": llm_config.get("temperature", 0.7),
                                "timeout": llm_config.get("timeout", 180),
                                "retry_times": llm_config.get("retry_times", 3),
                                "api_base": llm_config.get("api_base"),
                            }
                            logger.info(
                                f"✅ 读取深度模型配置: {deep_model} - {deep_model_config}"
                            )
                else:
                    logger.warning("⚠️ PostgreSQL 中没有找到系统配置，将使用默认参数")
            except Exception as e:
                logger.warning(f"⚠️ 从 PostgreSQL 读取模型配置失败: {e}，将使用默认参数")

            # 根据模型名称动态查找供应商（同步版本）
            normalize_provider_key = getattr(
                importlib.import_module("trader.llm.clients.providers"),
                "normalize_provider_key",
            )

            llm_provider = normalize_provider_key(
                get_provider_by_model_name_sync(quick_model)
            )

            # 使用标准配置函数创建完整配置
            create_analysis_config = getattr(
                importlib.import_module("app.services.analysis.simple"),
                "create_analysis_config",
            )
            config = create_analysis_config(
                research_depth=task.parameters.research_depth,
                selected_analysts=task.parameters.selected_analysts
                or ["market", "fundamentals"],
                quick_model=quick_model,
                deep_model=deep_model,
                llm_provider=llm_provider,
                market_type=getattr(task.parameters, "market_type", "A股"),
                quick_model_config=quick_model_config,  # 传递模型配置
                deep_model_config=deep_model_config,  # 传递模型配置
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

            # 在线程池中执行分析，避免阻塞事件循环
            asyncio = importlib.import_module("asyncio")
            importlib.import_module("concurrent.futures")
            concurrent = importlib.import_module("concurrent")

            loop = asyncio.get_event_loop()

            # 使用线程池执行器运行同步的分析代码
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor, self._execute_analysis_sync_with_progress, task, tracker
                )

            # 标记完成
            tracker.mark_completed()
            await self._update_task_status_with_tracker(
                task.task_id, AnalysisStatus.COMPLETED, tracker, result
            )

            # 记录 token 使用
            try:
                # 获取使用的模型信息
                quick_model = getattr(task.parameters, "quick_analysis_model", None)
                deep_model = getattr(task.parameters, "deep_analysis_model", None)

                # 优先使用深度分析模型，如果没有则使用快速分析模型
                model_name = deep_model or quick_model or "qwen-plus"

                # 根据模型名称确定供应商
                get_provider_by_model_name = getattr(
                    importlib.import_module("app.services.analysis.simple"),
                    "get_provider_by_model_name",
                )
                provider = await get_provider_by_model_name(model_name)

                # 记录使用情况
                await self._record_token_usage(task, result, provider, model_name)
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
