# ruff: noqa: F403,F405
from .common import *


class AnalysisSubmitMixin:
    async def submit_single_analysis(
        self, user_id: str, request: SingleAnalysisRequest
    ) -> Dict[str, Any]:
        """提交单股分析任务"""
        try:
            logger.info("📝 开始提交单股分析任务")
            logger.info(f"👤 用户ID: {user_id} (类型: {type(user_id)})")

            # 获取股票代码 (兼容旧字段)
            stock_symbol = request.get_symbol()
            logger.info(f"📊 股票代码: {stock_symbol}")
            logger.info(f"⚙️ 分析参数: {request.parameters}")

            # 生成任务ID
            task_id = str(uuid.uuid4())
            logger.info(f"🆔 生成任务ID: {task_id}")

            # 转换用户ID
            converted_user_id = self._convert_user_id(user_id)
            logger.info(
                f"🔄 转换后的用户ID: {converted_user_id} (类型: {type(converted_user_id)})"
            )

            # 创建分析任务
            logger.info("🏗️ 开始创建AnalysisTask对象...")

            # 读取合并后的系统设置（ENV 优先 → DB），用于填充模型与并发/超时配置
            try:
                effective_settings = (
                    await config_provider.get_effective_system_settings()
                )
            except Exception:
                effective_settings = {}

            # 填充分析参数中的模型（若请求未显式提供）
            params = request.parameters or AnalysisParameters()
            if not getattr(params, "quick_analysis_model", None):
                params.quick_analysis_model = effective_settings.get(
                    "quick_analysis_model", "qwen-turbo"
                )
            if not getattr(params, "deep_analysis_model", None):
                params.deep_analysis_model = effective_settings.get(
                    "deep_analysis_model", "qwen-max"
                )

            # 应用系统级并发与可见性超时（若提供）
            try:
                self.queue_service.user_concurrent_limit = int(
                    effective_settings.get(
                        "max_concurrent_tasks", DEFAULT_USER_CONCURRENT_LIMIT
                    )
                )
                self.queue_service.global_concurrent_limit = int(
                    effective_settings.get(
                        "max_concurrent_tasks", GLOBAL_CONCURRENT_LIMIT
                    )
                )
                self.queue_service.visibility_timeout = int(
                    effective_settings.get(
                        "default_analysis_timeout", VISIBILITY_TIMEOUT_SECONDS
                    )
                )
            except Exception:
                # 使用默认值即可
                pass

            task = AnalysisTask(
                task_id=task_id,
                user_id=converted_user_id,
                symbol=stock_symbol,
                stock_code=stock_symbol,  # 兼容字段
                parameters=params,
                status=AnalysisStatus.PENDING,
            )
            logger.info("✅ AnalysisTask对象创建成功")

            # 保存任务到数据库
            logger.info("💾 开始保存任务到数据库...")
            db = get_postgres_db()
            task_dict = task.model_dump(by_alias=True)
            logger.info(f"📄 任务字典: {task_dict}")
            await db.analysis_tasks.insert_one(task_dict)
            await dual_write_hot_document("analysis_tasks", task_dict)
            logger.info("✅ 任务已保存到数据库")

            # 单股分析：直接在后台执行（不阻塞API响应）
            logger.info("🚀 开始在后台执行分析任务...")

            # 创建后台任务，不等待完成
            asyncio = importlib.import_module("asyncio")
            asyncio.create_task(self._execute_single_analysis_async(task))

            # 不等待任务完成，让它在后台运行
            logger.info(f"✅ 后台任务已启动，任务ID: {task_id}")

            logger.info(f"🎉 单股分析任务提交完成: {task_id} - {stock_symbol}")

            return {
                "task_id": task_id,
                "symbol": stock_symbol,
                "stock_code": stock_symbol,  # 兼容字段
                "status": AnalysisStatus.PENDING,
                "message": "任务已在后台启动",
            }

        except Exception as e:
            logger.error(f"提交单股分析任务失败: {e}")
            raise

    async def submit_batch_analysis(
        self, user_id: str, request: BatchAnalysisRequest
    ) -> Dict[str, Any]:
        """提交批量分析任务"""
        try:
            # 生成批次ID
            batch_id = str(uuid.uuid4())

            # 转换用户ID
            converted_user_id = self._convert_user_id(user_id)

            # 读取系统设置，填充模型参数并应用并发/超时配置
            try:
                effective_settings = (
                    await config_provider.get_effective_system_settings()
                )
            except Exception:
                effective_settings = {}

            params = request.parameters or AnalysisParameters()
            if not getattr(params, "quick_analysis_model", None):
                params.quick_analysis_model = effective_settings.get(
                    "quick_analysis_model", "qwen-turbo"
                )
            if not getattr(params, "deep_analysis_model", None):
                params.deep_analysis_model = effective_settings.get(
                    "deep_analysis_model", "qwen-max"
                )

            try:
                self.queue_service.user_concurrent_limit = int(
                    effective_settings.get(
                        "max_concurrent_tasks", DEFAULT_USER_CONCURRENT_LIMIT
                    )
                )
                self.queue_service.global_concurrent_limit = int(
                    effective_settings.get(
                        "max_concurrent_tasks", GLOBAL_CONCURRENT_LIMIT
                    )
                )
                self.queue_service.visibility_timeout = int(
                    effective_settings.get(
                        "default_analysis_timeout", VISIBILITY_TIMEOUT_SECONDS
                    )
                )
            except Exception:
                pass

            # 创建批次记录
            # 获取股票代码列表 (兼容旧字段)
            stock_symbols = request.get_symbols()

            batch = AnalysisBatch(
                batch_id=batch_id,
                user_id=converted_user_id,
                title=request.title,
                description=request.description,
                total_tasks=len(stock_symbols),
                parameters=params,
                status=BatchStatus.PENDING,
            )

            # 创建任务列表
            tasks = []
            for symbol in stock_symbols:
                task_id = str(uuid.uuid4())
                task = AnalysisTask(
                    task_id=task_id,
                    batch_id=batch_id,
                    user_id=converted_user_id,
                    symbol=symbol,
                    stock_code=symbol,  # 兼容字段
                    parameters=batch.parameters,
                    status=AnalysisStatus.PENDING,
                )
                tasks.append(task)

            # 保存到数据库
            db = get_postgres_db()
            batch_document = batch.dict(by_alias=True)
            await db.analysis_batches.insert_one(batch_document)
            await dual_write_hot_document("analysis_batches", batch_document)
            task_documents = [task.dict(by_alias=True) for task in tasks]
            await db.analysis_tasks.insert_many(task_documents)
            await dual_write_hot_documents("analysis_tasks", task_documents)

            # 提交任务到队列
            for task in tasks:
                # 准备队列参数（直接传递分析参数，不嵌套）
                queue_params = task.parameters.dict() if task.parameters else {}

                # 添加任务元数据
                queue_params.update(
                    {
                        "task_id": task.task_id,
                        "symbol": task.symbol,
                        "stock_code": task.symbol,  # 兼容字段
                        "user_id": str(task.user_id),
                        "batch_id": task.batch_id,
                        "created_at": task.created_at.isoformat()
                        if task.created_at
                        else None,
                    }
                )

                # 调用队列服务
                await self.queue_service.enqueue_task(
                    user_id=str(converted_user_id),
                    symbol=task.symbol,
                    params=queue_params,
                    batch_id=task.batch_id,
                )

            logger.info(f"批量分析任务已提交: {batch_id} - {len(tasks)}个股票")

            return {
                "batch_id": batch_id,
                "total_tasks": len(tasks),
                "status": BatchStatus.PENDING,
                "message": f"已提交{len(tasks)}个分析任务到队列",
            }

        except Exception as e:
            logger.error(f"提交批量分析任务失败: {e}")
            raise
