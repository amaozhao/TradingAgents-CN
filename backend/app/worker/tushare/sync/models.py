from .imports import (
    Any,
    Dict,
    List,
    TaskCancelledException,
    asyncio,
    dual_write_hot_document,
    get_utc8_now,
    logger,
)

class _TushareSyncServiceMixin3:
    async def _process_news_batch(self, batch: List[str], hours_back: int, max_news_per_stock: int) -> Dict[str, Any]:
        """处理新闻批次"""
        batch_stats = {
            "success_count": 0,
            "error_count": 0,
            "news_count": 0,
            "errors": [],
        }

        for symbol in batch:
            try:
                # 从Tushare获取新闻数据
                news_data = await self.provider.get_stock_news(
                    symbol=symbol, limit=max_news_per_stock, hours_back=hours_back
                )

                if news_data:
                    # 保存新闻数据
                    saved_count = await self.news_service.save_news_data(
                        news_data=news_data, data_source="tushare", market="CN"
                    )

                    batch_stats["success_count"] += 1
                    batch_stats["news_count"] += saved_count

                    logger.debug(f"✅ {symbol} 新闻同步成功: {saved_count}条")
                else:
                    logger.debug(f"⚠️ {symbol} 未获取到新闻数据")
                    batch_stats["success_count"] += 1  # 没有新闻也算成功

                # 🔥 API限流：成功后休眠
                await asyncio.sleep(0.2)

            except Exception as e:
                batch_stats["error_count"] += 1
                error_msg = f"{symbol}: {str(e)}"
                batch_stats["errors"].append(error_msg)
                logger.error(f"❌ {symbol} 新闻同步失败: {e}")

                # 🔥 失败后也要休眠，避免"失败雪崩"
                # 失败时休眠更长时间，给API服务器恢复的机会
                await asyncio.sleep(1.0)

        return batch_stats

    async def _should_stop(self, job_id: str) -> bool:
        """
        检查任务是否应该停止

        Args:
            job_id: 任务ID

        Returns:
            是否应该停止
        """
        try:
            # 查询执行记录，检查 cancel_requested 标记
            execution = await self.db.scheduler_executions.find_one(
                {"job_id": job_id, "status": "running"}, sort=[("timestamp", -1)]
            )

            if execution and execution.get("cancel_requested"):
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 检查任务停止标记失败: {e}")
            return False

    async def _update_progress(self, job_id: str, progress: int, message: str):
        """
        更新任务进度

        Args:
            job_id: 任务ID
            progress: 进度百分比 (0-100)
            message: 进度消息
        """
        try:
            logger.info(f"📊 [进度更新] 开始更新任务 {job_id} 进度: {progress}% - {message}")

            # 查找最新的 running 记录
            execution = await self.db.scheduler_executions.find_one(
                {"job_id": job_id, "status": "running"}, sort=[("timestamp", -1)]
            )

            if not execution:
                logger.warning(f"⚠️ 未找到任务 {job_id} 的执行记录")
                return

            logger.info(f"📊 [进度更新] 找到执行记录: _id={execution['_id']}, 当前进度={execution.get('progress', 0)}%")

            # 检查是否收到取消请求
            if execution.get("cancel_requested"):
                raise TaskCancelledException(f"任务 {job_id} 已被用户取消")

            # 更新进度（使用 UTC+8 时间）
            updated_at = get_utc8_now()
            result = await self.db.scheduler_executions.update_one(
                {"_id": execution["_id"]},
                {
                    "$set": {
                        "progress": progress,
                        "progress_message": message,
                        "updated_at": updated_at,
                    }
                },
            )
            await dual_write_hot_document(
                "scheduler_executions",
                {
                    **execution,
                    "progress": progress,
                    "progress_message": message,
                    "updated_at": updated_at,
                },
            )

            logger.info(f"📊 [进度更新] 更新结果: matched={result.matched_count}, modified={result.modified_count}")
            logger.info(f"✅ 任务 {job_id} 进度更新成功: {progress}% - {message}")

        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新任务进度失败: {e}", exc_info=True)
