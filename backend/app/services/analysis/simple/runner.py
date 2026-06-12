from .common import (
    Any,
    Dict,
    Optional,
    RedisProgressTracker,
    SingleAnalysisRequest,
    TaskStatus,
    datetime,
    importlib,
    logger,
    traceback,
)
from .provider import (
    _dual_write_analysis_task_sync,
    create_analysis_config,
    get_provider_and_url_by_model_sync,
)
from .result import build_analysis_result


class AnalysisRunnerMixin:
    def _run_analysis_sync(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        tracker: Optional[RedisProgressTracker] = None,
    ) -> Dict[str, Any]:
        """同步执行分析的具体实现"""
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
                f"🔄 [线程池] 开始执行分析: {task_id} - {request.stock_code}"
            )
            logger.info(f"🔄 [线程池] 开始执行分析: {task_id} - {request.stock_code}")

            # 🔧 根据 RedisProgressTracker 的步骤权重计算准确的进度
            # 基础准备阶段 (10%): 0.03 + 0.02 + 0.01 + 0.02 + 0.02 = 0.10
            # 步骤索引 0-4 对应 0-10%

            # 异步更新进度（在线程池中调用）
            def update_progress_sync(progress: int, message: str, step: str):
                """在线程池中同步更新进度"""
                try:
                    # 同时更新 Redis 进度跟踪器
                    if tracker:
                        tracker.update_progress(
                            {"progress_percentage": progress, "last_message": message}
                        )

                    # 🔥 使用同步方式更新内存和 PostgreSQL，避免事件循环冲突
                    # 1. 更新内存中的任务状态（使用新事件循环）
                    asyncio = importlib.import_module("asyncio")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            self.memory_manager.update_task_status(
                                task_id=task_id,
                                status=TaskStatus.RUNNING,
                                progress=progress,
                                message=message,
                                current_step=step,
                            )
                        )
                    finally:
                        loop.close()

                    # 2. 更新PostgreSQL文档存储（同步接口，避免事件循环冲突）
                    get_postgres_db_sync = getattr(
                        importlib.import_module("app.core.database"),
                        "get_postgres_db_sync",
                    )
                    datetime = getattr(importlib.import_module("datetime"), "datetime")

                    sync_db = get_postgres_db_sync()

                    update_data = {
                        "progress": progress,
                        "current_step": step,
                        "message": message,
                        "updated_at": datetime.utcnow(),
                    }
                    sync_db.analysis_tasks.update_one(
                        {"task_id": task_id}, {"$set": update_data}
                    )
                    _dual_write_analysis_task_sync({"task_id": task_id, **update_data})
                except Exception as e:
                    logger.warning(f"⚠️ 进度更新失败: {e}")

            # 配置阶段 - 对应步骤3 "⚙️ 参数设置" (6-8%)
            update_progress_sync(7, "⚙️ 配置分析参数", "configuration")

            # 🆕 智能模型选择逻辑
            get_model_capability_service = getattr(
                importlib.import_module("app.services.capability"),
                "get_model_capability_service",
            )
            capability_service = get_model_capability_service()

            research_depth = (
                request.parameters.research_depth if request.parameters else "标准"
            )

            # 1. 检查前端是否指定了模型
            if (
                request.parameters
                and hasattr(request.parameters, "quick_analysis_model")
                and hasattr(request.parameters, "deep_analysis_model")
                and request.parameters.quick_analysis_model
                and request.parameters.deep_analysis_model
            ):
                # 使用前端指定的模型
                quick_model = request.parameters.quick_analysis_model
                deep_model = request.parameters.deep_analysis_model

                logger.info(
                    f"📝 [分析服务] 用户指定模型: quick={quick_model}, deep={deep_model}"
                )

                # 验证模型是否合适
                validation = capability_service.validate_model_pair(
                    quick_model, deep_model, research_depth
                )

                if not validation["valid"]:
                    # 记录警告
                    for warning in validation["warnings"]:
                        logger.warning(warning)

                    # 如果模型不合适，自动切换到推荐模型
                    logger.info("🔄 自动切换到推荐模型...")
                    quick_model, deep_model = (
                        capability_service.recommend_models_for_depth(research_depth)
                    )
                    logger.info(f"✅ 已切换: quick={quick_model}, deep={deep_model}")
                else:
                    # 即使验证通过，也记录警告信息
                    for warning in validation["warnings"]:
                        logger.info(warning)
                    logger.info(
                        f"✅ 用户选择的模型验证通过: quick={quick_model}, deep={deep_model}"
                    )

            else:
                # 2. 自动推荐模型
                quick_model, deep_model = capability_service.recommend_models_for_depth(
                    research_depth
                )
                logger.info(f"🤖 自动推荐模型: quick={quick_model}, deep={deep_model}")

            # 🔧 根据快速模型和深度模型分别查找对应的供应商和 API URL
            quick_provider_info = get_provider_and_url_by_model_sync(quick_model)
            deep_provider_info = get_provider_and_url_by_model_sync(deep_model)

            quick_provider = quick_provider_info["provider"]
            deep_provider = deep_provider_info["provider"]
            quick_backend_url = quick_provider_info["backend_url"]
            deep_backend_url = deep_provider_info["backend_url"]

            logger.info(
                f"🔍 [供应商查找] 快速模型 {quick_model} 对应的供应商: {quick_provider}"
            )
            logger.info(f"🔍 [API地址] 快速模型使用 backend_url: {quick_backend_url}")
            logger.info(
                f"🔍 [供应商查找] 深度模型 {deep_model} 对应的供应商: {deep_provider}"
            )
            logger.info(f"🔍 [API地址] 深度模型使用 backend_url: {deep_backend_url}")

            # 检查两个模型是否来自同一个厂家
            if quick_provider == deep_provider:
                logger.info(f"✅ [供应商验证] 两个模型来自同一厂家: {quick_provider}")
            else:
                logger.info(
                    f"✅ [混合模式] 快速模型({quick_provider}) 和 深度模型({deep_provider}) 来自不同厂家"
                )

            # 获取市场类型
            market_type = (
                request.parameters.market_type if request.parameters else "A股"
            )
            logger.info(f"📊 [市场类型] 使用市场类型: {market_type}")

            # 创建分析配置（支持混合模式）
            config = create_analysis_config(
                research_depth=research_depth,
                selected_analysts=request.parameters.selected_analysts
                if request.parameters
                else ["market", "fundamentals"],
                quick_model=quick_model,
                deep_model=deep_model,
                llm_provider=quick_provider,  # 主要使用快速模型的供应商
                market_type=market_type,  # 使用前端传递的市场类型
            )

            # 🔧 添加混合模式配置
            config["quick_provider"] = quick_provider
            config["deep_provider"] = deep_provider
            config["quick_backend_url"] = quick_backend_url
            config["deep_backend_url"] = deep_backend_url
            config["backend_url"] = quick_backend_url  # 保持向后兼容

            # 🔍 验证配置中的模型
            logger.info(
                f"🔍 [模型验证] 配置中的快速模型: {config.get('quick_think_llm')}"
            )
            logger.info(
                f"🔍 [模型验证] 配置中的深度模型: {config.get('deep_think_llm')}"
            )
            logger.info(
                f"🔍 [模型验证] 配置中的LLM供应商: {config.get('llm_provider')}"
            )

            # 初始化分析引擎 - 对应步骤4 "🚀 启动引擎" (8-10%)
            update_progress_sync(9, "🚀 初始化AI分析引擎", "engine_initialization")
            trading_graph = self._get_trading_graph(config)

            # 🔍 验证TradingGraph实例中的配置
            logger.info(
                f"🔍 [引擎验证] TradingGraph配置中的快速模型: {trading_graph.config.get('quick_think_llm')}"
            )
            logger.info(
                f"🔍 [引擎验证] TradingGraph配置中的深度模型: {trading_graph.config.get('deep_think_llm')}"
            )

            # 准备分析数据
            start_time = datetime.now()

            # 🔧 使用前端传递的分析日期，如果没有则使用当前日期
            if (
                request.parameters
                and hasattr(request.parameters, "analysis_date")
                and request.parameters.analysis_date
            ):
                # 前端传递的是 datetime 对象或字符串
                if isinstance(request.parameters.analysis_date, datetime):
                    analysis_date = request.parameters.analysis_date.strftime(
                        "%Y-%m-%d"
                    )
                elif isinstance(request.parameters.analysis_date, str):
                    analysis_date = request.parameters.analysis_date
                else:
                    analysis_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"📅 使用前端指定的分析日期: {analysis_date}")
            else:
                analysis_date = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"📅 使用当前日期作为分析日期: {analysis_date}")

            # 🔧 智能日期范围处理：获取最近10天的数据，自动处理周末/节假日
            # 这样可以确保即使是周末或节假日，也能获取到最后一个交易日的数据
            get_trading_date_range = getattr(
                importlib.import_module("trader.utils.flows"), "get_trading_date_range"
            )
            data_start_date, data_end_date = get_trading_date_range(
                analysis_date, lookback_days=10
            )

            logger.info(f"📅 分析目标日期: {analysis_date}")
            logger.info(
                f"📅 数据查询范围: {data_start_date} 至 {data_end_date} (最近10天)"
            )
            logger.info("💡 说明: 获取10天数据可自动处理周末、节假日和数据延迟问题")

            # 开始分析 - 进度10%，即将进入分析师阶段
            # 注意：不要手动设置过高的进度，让 graph_progress_callback 来更新实际的分析进度
            update_progress_sync(10, "🤖 开始多智能体协作分析", "agent_analysis")

            # 启动一个异步任务来模拟进度更新
            threading = importlib.import_module("threading")
            time = importlib.import_module("time")

            def simulate_progress():
                """模拟分析引擎内部进度"""
                try:
                    if not tracker:
                        return

                    # 分析师阶段 - 根据选择的分析师数量动态调整
                    analysts = (
                        request.parameters.selected_analysts
                        if request.parameters
                        else ["market", "fundamentals"]
                    )

                    # 模拟分析师执行
                    for i, analyst in enumerate(analysts):
                        time.sleep(15)  # 每个分析师大约15秒
                        if analyst == "market":
                            tracker.update_progress("📊 市场分析师正在分析")
                        elif analyst == "fundamentals":
                            tracker.update_progress("💼 基本面分析师正在分析")
                        elif analyst == "news":
                            tracker.update_progress("📰 新闻分析师正在分析")
                        elif analyst == "social":
                            tracker.update_progress("💬 社交媒体分析师正在分析")

                    # 研究团队阶段
                    time.sleep(10)
                    tracker.update_progress("🐂 看涨研究员构建论据")

                    time.sleep(8)
                    tracker.update_progress("🐻 看跌研究员识别风险")

                    # 辩论阶段 - 根据5个级别确定辩论轮次
                    research_depth = (
                        request.parameters.research_depth
                        if request.parameters
                        else "标准"
                    )
                    if research_depth == "快速":
                        debate_rounds = 1
                    elif research_depth == "基础":
                        debate_rounds = 1
                    elif research_depth == "标准":
                        debate_rounds = 1
                    elif research_depth == "深度":
                        debate_rounds = 2
                    elif research_depth == "全面":
                        debate_rounds = 3
                    else:
                        debate_rounds = 1  # 默认

                    for round_num in range(debate_rounds):
                        time.sleep(12)
                        tracker.update_progress(f"🎯 研究辩论 第{round_num + 1}轮")

                    time.sleep(8)
                    tracker.update_progress("👔 研究经理形成共识")

                    # 交易员阶段
                    time.sleep(10)
                    tracker.update_progress("💼 交易员制定策略")

                    # 风险管理阶段
                    time.sleep(8)
                    tracker.update_progress("🔥 激进风险评估")

                    time.sleep(6)
                    tracker.update_progress("🛡️ 保守风险评估")

                    time.sleep(6)
                    tracker.update_progress("⚖️ 中性风险评估")

                    time.sleep(8)
                    tracker.update_progress("🎯 风险经理制定策略")

                    # 最终阶段
                    time.sleep(5)
                    tracker.update_progress("📡 信号处理")

                except Exception as e:
                    logger.warning(f"⚠️ 进度模拟失败: {e}")

            # 启动进度模拟线程
            progress_thread = threading.Thread(target=simulate_progress, daemon=True)
            progress_thread.start()

            # 定义进度回调函数，用于接收 LangGraph 的实时进度
            # 节点进度映射表（与 RedisProgressTracker 的步骤权重对应）
            node_progress_map = {
                # 分析师阶段 (10% → 45%)
                "📊 市场分析师": 27.5,  # 10% + 17.5% (假设2个分析师)
                "💼 基本面分析师": 45,  # 10% + 35%
                "📰 新闻分析师": 27.5,  # 如果有3个分析师
                "💬 社交媒体分析师": 27.5,  # 如果有4个分析师
                # 研究辩论阶段 (45% → 70%)
                "🐂 看涨研究员": 51.25,  # 45% + 6.25%
                "🐻 看跌研究员": 57.5,  # 45% + 12.5%
                "👔 研究经理": 70,  # 45% + 25%
                # 交易员阶段 (70% → 78%)
                "💼 交易员决策": 78,  # 70% + 8%
                # 风险评估阶段 (78% → 93%)
                "🔥 激进风险评估": 81.75,  # 78% + 3.75%
                "🛡️ 保守风险评估": 85.5,  # 78% + 7.5%
                "⚖️ 中性风险评估": 89.25,  # 78% + 11.25%
                "🎯 风险经理": 93,  # 78% + 15%
                # 最终阶段 (93% → 100%)
                "📊 生成报告": 97,  # 93% + 4%
            }

            def graph_progress_callback(message: str):
                """接收 LangGraph 的进度更新

                根据节点名称直接映射到进度百分比，确保与 RedisProgressTracker 的步骤权重一致
                注意：只在进度增加时更新，避免覆盖 RedisProgressTracker 的虚拟步骤进度
                """
                try:
                    logger.info(f"🎯🎯🎯 [Graph进度回调被调用] message={message}")
                    if not tracker:
                        logger.warning("⚠️ tracker 为 None，无法更新进度")
                        return

                    # 查找节点对应的进度百分比
                    progress_pct = node_progress_map.get(message)

                    if progress_pct is not None:
                        # 获取当前进度（使用 progress_data 属性）
                        current_progress = tracker.progress_data.get(
                            "progress_percentage", 0
                        )

                        # 只在进度增加时更新，避免覆盖虚拟步骤的进度
                        if int(progress_pct) > current_progress:
                            # 更新 Redis 进度跟踪器
                            tracker.update_progress(
                                {
                                    "progress_percentage": int(progress_pct),
                                    "last_message": message,
                                }
                            )
                            logger.info(
                                f"📊 [Graph进度] 进度已更新: {current_progress}% → {int(progress_pct)}% - {message}"
                            )

                            # 🔥 同时更新内存和 PostgreSQL
                            try:
                                asyncio = importlib.import_module("asyncio")
                                datetime = getattr(
                                    importlib.import_module("datetime"), "datetime"
                                )

                                # 尝试获取当前运行的事件循环
                                try:
                                    loop = asyncio.get_running_loop()
                                    # 如果在事件循环中，使用 create_task
                                    asyncio.create_task(
                                        self._update_progress_async(
                                            task_id, int(progress_pct), message
                                        )
                                    )
                                    logger.debug(
                                        f"✅ [Graph进度] 已提交异步更新任务: {int(progress_pct)}%"
                                    )
                                except RuntimeError:
                                    # 没有运行的事件循环，使用同步方式更新PostgreSQL文档存储
                                    get_postgres_db_sync = getattr(
                                        importlib.import_module("app.core.database"),
                                        "get_postgres_db_sync",
                                    )
                                    sync_db = get_postgres_db_sync()

                                    # 同步更新 PostgreSQL
                                    update_data = {
                                        "progress": int(progress_pct),
                                        "current_step": message,
                                        "message": message,
                                        "updated_at": datetime.utcnow(),
                                    }
                                    sync_db.analysis_tasks.update_one(
                                        {"task_id": task_id}, {"$set": update_data}
                                    )
                                    _dual_write_analysis_task_sync(
                                        {"task_id": task_id, **update_data}
                                    )
                                    # 异步更新内存（创建新的事件循环）
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    try:
                                        loop.run_until_complete(
                                            self.memory_manager.update_task_status(
                                                task_id=task_id,
                                                status=TaskStatus.RUNNING,
                                                progress=int(progress_pct),
                                                message=message,
                                                current_step=message,
                                            )
                                        )
                                    finally:
                                        loop.close()

                                    logger.debug(
                                        f"✅ [Graph进度] 已同步更新内存和PostgreSQL: {int(progress_pct)}%"
                                    )
                            except Exception as sync_err:
                                logger.warning(
                                    f"⚠️ [Graph进度] 同步更新失败: {sync_err}"
                                )
                        else:
                            # 进度没有增加，只更新消息
                            tracker.update_progress({"last_message": message})
                            logger.info(
                                f"📊 [Graph进度] 进度未变化({current_progress}% >= {int(progress_pct)}%)，仅更新消息: {message}"
                            )
                    else:
                        # 未知节点，只更新消息
                        logger.warning(f"⚠️ [Graph进度] 未知节点: {message}，仅更新消息")
                        tracker.update_progress({"last_message": message})

                except Exception as e:
                    logger.error(f"❌ Graph进度回调失败: {e}", exc_info=True)

            logger.info(
                f"🚀 准备调用 trading_graph.propagate，progress_callback={graph_progress_callback}"
            )

            # 执行实际分析，传递进度回调和task_id
            state, decision = trading_graph.propagate(
                request.stock_code,
                analysis_date,
                progress_callback=graph_progress_callback,
                task_id=task_id,
            )

            logger.info("✅ trading_graph.propagate 执行完成")

            # 🔍 调试：检查decision的结构
            logger.info(f"🔍 [DEBUG] Decision类型: {type(decision)}")
            logger.info(f"🔍 [DEBUG] Decision内容: {decision}")
            if isinstance(decision, dict):
                logger.info(f"🔍 [DEBUG] Decision键: {list(decision.keys())}")
            elif hasattr(decision, "__dict__"):
                logger.info(f"🔍 [DEBUG] Decision属性: {list(vars(decision).keys())}")

            # 处理结果
            if tracker:
                tracker.update_progress("📊 处理分析结果")
            update_progress_sync(90, "处理分析结果...", "result_processing")

            execution_time = (datetime.now() - start_time).total_seconds()

            return build_analysis_result(
                request=request,
                analysis_date=analysis_date,
                state=state,
                decision=decision,
                execution_time=execution_time,
                task_id=task_id,
            )
        except Exception as e:
            logger.error(f"❌ [线程池] 分析执行失败: {task_id} - {e}", exc_info=True)
            logger.error(
                "❌ [线程池] 分析执行完整 traceback: task_id=%s\n%s",
                task_id,
                "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            )

            # 格式化错误信息为用户友好的提示
            ErrorFormatter = getattr(
                importlib.import_module("app.utils.errors"), "ErrorFormatter"
            )

            # 收集上下文信息
            error_context = {}
            if request and hasattr(request, "parameters") and request.parameters:
                quick_model = getattr(request.parameters, "quick_analysis_model", None)
                deep_model = getattr(request.parameters, "deep_analysis_model", None)
                if quick_model:
                    error_context["model"] = quick_model
                if deep_model:
                    error_context["model"] = deep_model
                try:
                    if quick_model:
                        provider_info = get_provider_and_url_by_model_sync(quick_model)
                        error_context["llm_provider"] = provider_info.get("provider")
                        error_context["backend_url"] = provider_info.get("backend_url")
                except Exception as context_error:
                    logger.warning(
                        "⚠️ [错误上下文] 获取模型供应商失败: %s", context_error
                    )

            # 格式化错误
            formatted_error = ErrorFormatter.format_error(str(e), error_context)

            # 构建用户友好的错误消息，并保留原始技术细节用于排查。
            technical_detail = formatted_error.get("technical_detail") or str(e)
            user_friendly_error = (
                f"{formatted_error['title']}\n\n"
                f"{formatted_error['message']}\n\n"
                f"💡 {formatted_error['suggestion']}\n\n"
                f"技术细节：{technical_detail}"
            )

            # 抛出包含友好错误信息的异常
            raise Exception(user_friendly_error) from e
