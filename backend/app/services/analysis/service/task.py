from .common import (
    AnalysisResult,
    AnalysisStatus,
    AnalysisTask,
    Callable,
    Optional,
    create_analysis_config_async,
    datetime,
    get_provider_by_model_name,
    importlib,
    logger,
    uuid,
)


class AnalysisTaskMixin:
    async def execute_analysis_task(
        self,
        task: AnalysisTask,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> AnalysisResult:
        """执行单个分析任务"""
        try:
            logger.info(f"开始执行分析任务: {task.task_id} - {task.symbol}")

            # 更新任务状态
            await self._update_task_status(task.task_id, AnalysisStatus.PROCESSING, 0)

            if progress_callback:
                progress_callback(10, "初始化分析引擎...")

            # 使用标准配置函数创建完整配置 - 与个股分析保持一致
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

            # 🔧 从数据库读取模型的完整配置参数
            quick_model_config = None
            deep_model_config = None
            llm_configs = unified_config.get_llm_configs()

            for llm_config in llm_configs:
                if llm_config.model_name == quick_model:
                    quick_model_config = {
                        "max_tokens": llm_config.max_tokens,
                        "temperature": llm_config.temperature,
                        "timeout": llm_config.timeout,
                        "retry_times": llm_config.retry_times,
                        "api_base": llm_config.api_base,
                    }

                if llm_config.model_name == deep_model:
                    deep_model_config = {
                        "max_tokens": llm_config.max_tokens,
                        "temperature": llm_config.temperature,
                        "timeout": llm_config.timeout,
                        "retry_times": llm_config.retry_times,
                        "api_base": llm_config.api_base,
                    }

            # 根据模型名称动态查找供应商
            normalize_provider_key = getattr(
                importlib.import_module("trader.llm.clients.providers"),
                "normalize_provider_key",
            )

            llm_provider = normalize_provider_key(
                await get_provider_by_model_name(quick_model)
            )

            # 使用标准配置函数创建完整配置
            config = await create_analysis_config_async(
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

            if progress_callback:
                progress_callback(30, "创建分析图...")

            # 获取分析引擎实例
            trading_graph = self._get_trading_graph(config)

            if progress_callback:
                progress_callback(50, "执行股票分析...")

            # 执行分析
            start_time = datetime.utcnow()
            analysis_date = task.parameters.analysis_date or datetime.now().strftime(
                "%Y-%m-%d"
            )

            # 调用现有的分析方法
            _, decision = trading_graph.propagate(task.symbol, analysis_date)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            if progress_callback:
                progress_callback(80, "处理分析结果...")

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

            if progress_callback:
                progress_callback(100, "分析完成")

            # 更新任务状态
            await self._update_task_status(
                task.task_id, AnalysisStatus.COMPLETED, 100, result
            )

            # 记录 token 使用
            try:
                # 记录使用情况
                await self._record_token_usage(
                    task, result, llm_provider, deep_model or quick_model
                )
            except Exception as e:
                logger.error(f"⚠️  记录 token 使用失败: {e}")

            logger.info(f"分析任务完成: {task.task_id} - 耗时{execution_time:.2f}秒")

            return result

        except Exception as e:
            logger.error(f"执行分析任务失败: {task.task_id} - {e}")

            # 更新任务状态为失败
            error_result = AnalysisResult(error_message=str(e))
            await self._update_task_status(
                task.task_id, AnalysisStatus.FAILED, 0, error_result
            )

            raise
