# ruff: noqa: F403,F405
from .common import *


class AnalysisTaskMixin:
    async def create_analysis_task(
        self, user_id: str, request: SingleAnalysisRequest
    ) -> Dict[str, Any]:
        """创建分析任务（立即返回，不执行分析）"""
        try:
            # 生成任务ID
            task_id = str(uuid.uuid4())

            # 🔧 使用 get_symbol() 方法获取股票代码（兼容 symbol 和 stock_code 字段）
            stock_code = request.get_symbol()
            if not stock_code:
                raise ValueError("股票代码不能为空")

            logger.info(f"📝 创建分析任务: {task_id} - {stock_code}")
            logger.info(f"🔍 内存管理器实例ID: {id(self.memory_manager)}")

            # 在内存中创建任务状态
            task_state = await self.memory_manager.create_task(
                task_id=task_id,
                user_id=user_id,
                stock_code=stock_code,
                parameters=request.parameters.model_dump()
                if request.parameters
                else {},
                stock_name=(
                    self._resolve_stock_name(stock_code)
                    if hasattr(self, "_resolve_stock_name")
                    else None
                ),
            )

            logger.info(f"✅ 任务状态已创建: {task_state.task_id}")

            # 立即验证任务是否可以查询到
            verify_task = await self.memory_manager.get_task(task_id)
            if verify_task:
                logger.info(f"✅ 任务创建验证成功: {verify_task.task_id}")
            else:
                logger.error(f"❌ 任务创建验证失败: 无法查询到刚创建的任务 {task_id}")

            # 补齐股票名称并写入数据库任务文档的初始记录
            code = stock_code
            name = (
                self._resolve_stock_name(code)
                if hasattr(self, "_resolve_stock_name")
                else f"股票{code}"
            )

            try:
                db = get_postgres_db()
                task_document = {
                    "task_id": task_id,
                    "user_id": user_id,
                    "stock_code": code,
                    "stock_symbol": code,
                    "stock_name": name,
                    "status": "pending",
                    "progress": 0,
                    "created_at": datetime.utcnow(),
                }
                result = await db.analysis_tasks.update_one(
                    {"task_id": task_id}, {"$setOnInsert": task_document}, upsert=True
                )
                await dual_write_hot_document("analysis_tasks", task_document)

                if result.upserted_id or result.matched_count > 0:
                    logger.info(f"✅ 任务已保存到 PostgreSQL document store: {task_id}")
                else:
                    logger.warning(
                        f"⚠️ PostgreSQL document store 保存结果异常: matched={result.matched_count}, upserted={result.upserted_id}"
                    )

            except Exception as e:
                logger.error(f"❌ 创建任务时写入 PostgreSQL document store 失败: {e}")
                # 这里不应该忽略错误，因为没有 document-store 记录会导致状态查询失败
                # 但为了不影响任务执行，我们记录错误但继续执行
                traceback = importlib.import_module("traceback")
                logger.error(
                    f"❌ PostgreSQL document store 保存详细错误: {traceback.format_exc()}"
                )

            return {
                "task_id": task_id,
                "status": "pending",
                "message": "任务已创建，等待执行",
            }

        except Exception as e:
            logger.error(f"❌ 创建分析任务失败: {e}")
            raise

    async def execute_analysis_background(
        self, task_id: str, user_id: str, request: SingleAnalysisRequest
    ):
        """在后台执行分析任务"""
        # 🔧 使用 get_symbol() 方法获取股票代码（兼容 symbol 和 stock_code 字段）
        stock_code = request.get_symbol()

        # 添加最外层的异常捕获，确保所有异常都被记录
        try:
            logger.info(
                f"🎯🎯🎯 [ENTRY] execute_analysis_background 方法被调用: {task_id}"
            )
            logger.info(f"🎯🎯🎯 [ENTRY] user_id={user_id}, stock_code={stock_code}")
        except Exception as entry_error:
            print(f"❌❌❌ [CRITICAL] 日志记录失败: {entry_error}")
            traceback = importlib.import_module("traceback")
            traceback.print_exc()

        tracker = None
        try:
            logger.info(f"🚀 开始后台执行分析任务: {task_id}")

            # 🔍 验证股票代码是否存在
            logger.info(f"🔍 开始验证股票代码: {stock_code}")
            prepare_stock_data_async = getattr(
                importlib.import_module("trader.utils.validation"),
                "prepare_stock_data_async",
            )
            datetime = getattr(importlib.import_module("datetime"), "datetime")

            # 获取市场类型
            market_type = (
                request.parameters.market_type if request.parameters else "A股"
            )

            # 获取分析日期并转换为字符串格式
            analysis_date = (
                request.parameters.analysis_date if request.parameters else None
            )
            if analysis_date:
                # 如果是 datetime 对象，转换为字符串
                if isinstance(analysis_date, datetime):
                    analysis_date = analysis_date.strftime("%Y-%m-%d")
                # 如果是字符串，确保格式正确
                elif isinstance(analysis_date, str):
                    # 尝试解析并重新格式化，确保格式统一
                    try:
                        parsed_date = datetime.strptime(analysis_date, "%Y-%m-%d")
                        analysis_date = parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        # 如果格式不对，使用今天
                        analysis_date = datetime.now().strftime("%Y-%m-%d")
                        logger.warning(
                            f"⚠️ 分析日期格式不正确，使用今天: {analysis_date}"
                        )

            # 🔥 使用异步版本，直接 await，避免事件循环冲突
            validation_result = await prepare_stock_data_async(
                stock_code=stock_code,
                market_type=market_type,
                period_days=30,
                analysis_date=analysis_date,
            )

            if not validation_result.is_valid:
                error_msg = f"❌ 股票代码验证失败: {validation_result.error_message}"
                logger.error(error_msg)
                logger.error(f"💡 建议: {validation_result.suggestion}")

                # 构建用户友好的错误消息
                user_friendly_error = f"❌ 股票代码无效\n\n{validation_result.error_message}\n\n💡 {validation_result.suggestion}"

                # 更新任务状态为失败
                await self.memory_manager.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    progress=0,
                    error_message=user_friendly_error,
                )

                # 更新PostgreSQL状态
                await self._update_task_status(
                    task_id, AnalysisStatus.FAILED, 0, error_message=user_friendly_error
                )

                return

            logger.info(
                f"✅ 股票代码验证通过: {stock_code} - {validation_result.stock_name}"
            )
            logger.info(f"📊 市场类型: {validation_result.market_type}")
            logger.info(
                f"📈 历史数据: {'有' if validation_result.has_historical_data else '无'}"
            )
            logger.info(
                f"📋 基本信息: {'有' if validation_result.has_basic_info else '无'}"
            )

            request_parameters = request.parameters or AnalysisParameters()

            # 在线程池中创建Redis进度跟踪器（避免阻塞事件循环）
            def create_tracker():
                """在线程中创建进度跟踪器"""
                logger.info(f"📊 [线程] 创建进度跟踪器: {task_id}")
                tracker = RedisProgressTracker(
                    task_id=task_id,
                    analysts=request_parameters.selected_analysts
                    or ["market", "fundamentals"],
                    research_depth=request_parameters.research_depth or "标准",
                    llm_provider="dashscope",
                )
                logger.info(f"✅ [线程] 进度跟踪器创建完成: {task_id}")
                return tracker

            tracker = await asyncio.to_thread(create_tracker)

            # 缓存进度跟踪器
            self._trackers[task_id] = tracker

            # 注册到日志监控
            register_analysis_tracker(task_id, tracker)

            # 初始化进度（在线程中执行）
            await asyncio.to_thread(
                tracker.update_progress,
                {"progress_percentage": 10, "last_message": "🚀 开始股票分析"},
            )

            # 更新状态为运行中
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=10,
                message="分析开始...",
                current_step="initialization",
            )

            # 同步更新PostgreSQL状态
            await self._update_task_status(task_id, AnalysisStatus.PROCESSING, 10)

            # 数据准备阶段（在线程中执行）
            await asyncio.to_thread(
                tracker.update_progress,
                {"progress_percentage": 20, "last_message": "🔧 检查环境配置"},
            )
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=20,
                message="准备分析数据...",
                current_step="data_preparation",
            )

            # 同步更新PostgreSQL状态
            await self._update_task_status(task_id, AnalysisStatus.PROCESSING, 20)

            # 执行实际的分析
            result = await self._execute_analysis_sync(
                task_id, user_id, request, tracker
            )

            # 标记进度跟踪器完成（在线程中执行）
            await asyncio.to_thread(tracker.mark_completed)

            # 保存分析结果到文件和数据库
            try:
                logger.info(f"💾 开始保存分析结果: {task_id}")
                await self._save_analysis_complete(task_id, result)
                logger.info(f"✅ 分析结果保存完成: {task_id}")
            except Exception as save_error:
                logger.error(f"❌ 保存分析结果失败: {task_id} - {save_error}")
                # 保存失败不影响分析完成状态

            # 🔍 调试：检查即将保存到内存的result
            logger.info(f"🔍 [DEBUG] 即将保存到内存的result键: {list(result.keys())}")
            logger.info(
                f"🔍 [DEBUG] 即将保存到内存的decision: {bool(result.get('decision'))}"
            )
            if result.get("decision"):
                logger.info(f"🔍 [DEBUG] 即将保存的decision内容: {result['decision']}")

            # 更新状态为完成
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                message="分析完成",
                current_step="completed",
                result_data=result,
            )

            # 同步更新PostgreSQL状态为完成
            await self._update_task_status(task_id, AnalysisStatus.COMPLETED, 100)
            self._clear_analysis_checkpoint_after_completion(request, result)

            # 创建通知：分析完成（方案B：REST+SSE）
            try:
                get_notifications_service = getattr(
                    importlib.import_module("app.services.notification"),
                    "get_notifications_service",
                )
                svc = get_notifications_service()
                summary = str(result.get("summary", ""))[:120]
                await svc.create_and_publish(
                    payload=NotificationCreate(
                        user_id=str(user_id),
                        type="analysis",
                        title=f"{request.stock_code} 分析完成",
                        content=summary,
                        link=f"/stocks/{request.stock_code}",
                        source="analysis",
                    )
                )
            except Exception as notif_err:
                logger.warning(f"⚠️ 创建通知失败(忽略): {notif_err}")

            logger.info(f"✅ 后台分析任务完成: {task_id}")

        except Exception as e:
            logger.error(f"❌ 后台分析任务失败: {task_id} - {e}", exc_info=True)

            # 格式化错误信息为用户友好的提示
            ErrorFormatter = getattr(
                importlib.import_module("app.utils.errors"), "ErrorFormatter"
            )

            # 收集上下文信息
            error_context = {}
            if hasattr(request, "parameters") and request.parameters:
                quick_model = getattr(request.parameters, "quick_analysis_model", None)
                deep_model = getattr(request.parameters, "deep_analysis_model", None)
                if quick_model:
                    error_context["model"] = quick_model
                if deep_model:
                    error_context["model"] = deep_model

            # 格式化错误
            formatted_error = ErrorFormatter.format_error(str(e), error_context)

            # 构建用户友好的错误消息，并保留原始异常，避免状态页只显示“未知错误”。
            technical_detail = formatted_error.get("technical_detail") or str(e)
            user_friendly_error = (
                f"{formatted_error['title']}\n\n"
                f"{formatted_error['message']}\n\n"
                f"💡 {formatted_error['suggestion']}\n\n"
                f"技术细节：{type(e).__name__}: {technical_detail}"
            )

            # 标记进度跟踪器失败
            if tracker:
                tracker.mark_failed(user_friendly_error)

            # 更新状态为失败
            await self.memory_manager.update_task_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                progress=0,
                message="分析失败",
                current_step="failed",
                error_message=user_friendly_error,
            )

            # 同步更新PostgreSQL状态为失败
            await self._update_task_status(
                task_id, AnalysisStatus.FAILED, 0, user_friendly_error
            )
        finally:
            # 清理进度跟踪器缓存
            if task_id in self._trackers:
                del self._trackers[task_id]

            # 从日志监控中注销
            unregister_analysis_tracker(task_id)

    def _clear_analysis_checkpoint_after_completion(
        self, request: SingleAnalysisRequest, result: Dict[str, Any]
    ) -> None:
        """Clear graph checkpoints only after the whole task is completed."""
        try:
            DEFAULT_CONFIG = getattr(
                importlib.import_module("trader.default"), "DEFAULT_CONFIG"
            )
            clear_checkpoint = getattr(
                importlib.import_module("trader.graph.checkpointer"),
                "clear_checkpoint",
            )
            stock_code = result.get("stock_code") or request.get_symbol()
            analysis_date = result.get("analysis_date")
            if not stock_code or not analysis_date:
                logger.warning("⚠️ 无法清理 checkpoint：缺少股票代码或分析日期")
                return
            clear_checkpoint(
                DEFAULT_CONFIG["data_cache_dir"], stock_code, analysis_date
            )
            logger.info(
                "🧹 [Checkpoint] 任务完成后已清理 checkpoint: %s %s",
                stock_code,
                analysis_date,
            )
        except Exception as checkpoint_error:
            logger.warning("⚠️ 清理 checkpoint 失败: %s", checkpoint_error)

    async def _execute_analysis_sync(
        self,
        task_id: str,
        user_id: str,
        request: SingleAnalysisRequest,
        tracker: Optional[RedisProgressTracker] = None,
    ) -> Dict[str, Any]:
        """同步执行分析（在共享线程池中运行）"""
        # 🔧 使用共享线程池，支持多个任务并发执行
        # 不再每次创建新的线程池，避免串行执行
        loop = asyncio.get_event_loop()
        logger.info(
            f"🚀 [线程池] 提交分析任务到共享线程池: {task_id} - {request.stock_code}"
        )
        result = await loop.run_in_executor(
            self._thread_pool,  # 使用共享线程池
            self._run_analysis_sync,
            task_id,
            user_id,
            request,
            tracker,
        )
        logger.info(f"✅ [线程池] 分析任务执行完成: {task_id}")
        return result
