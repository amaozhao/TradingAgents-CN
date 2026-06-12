from .common import (
    Any,
    Dict,
    Optional,
    dual_write_hot_document,
    get_utc8_now,
    logger,
)


class SchedulerMetadataMixin:
    async def _record_job_action(
        self, job_id: str, action: str, status: str, error_message: Optional[str] = None
    ):
        """
        记录任务操作历史

        Args:
            job_id: 任务ID
            action: 操作类型 (pause/resume/trigger)
            status: 状态 (success/failed)
            error_message: 错误信息
        """
        try:
            db = self._get_db()
            history_doc = {
                "job_id": job_id,
                "action": action,
                "status": status,
                "error_message": error_message,
                "timestamp": get_utc8_now(),
            }
            result = await db.scheduler_history.insert_one(history_doc)
            history_doc["_id"] = result.inserted_id
            await self._dual_write_scheduler_document("scheduler_history", history_doc)
        except Exception as e:
            logger.error(f"❌ 记录任务操作历史失败: {e}")

    async def _get_job_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务元数据（触发器名称和备注）

        Args:
            job_id: 任务ID

        Returns:
            元数据字典，如果不存在则返回None
        """
        try:
            db = self._get_db()
            metadata = await db.scheduler_metadata.find_one({"job_id": job_id})
            if metadata:
                metadata.pop("_id", None)
                return metadata
            return None
        except Exception as e:
            logger.error(f"❌ 获取任务 {job_id} 元数据失败: {e}")
            return None

    async def update_job_metadata(
        self,
        job_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        更新任务元数据

        Args:
            job_id: 任务ID
            display_name: 触发器名称
            description: 备注

        Returns:
            是否成功
        """
        try:
            # 检查任务是否存在
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"❌ 任务 {job_id} 不存在")
                return False

            db = self._get_db()
            update_data = {"job_id": job_id, "updated_at": get_utc8_now()}

            if display_name is not None:
                update_data["display_name"] = display_name
            if description is not None:
                update_data["description"] = description

            # 使用 upsert 更新或插入
            await db.scheduler_metadata.update_one(
                {"job_id": job_id}, {"$set": update_data}, upsert=True
            )
            await self._dual_write_scheduler_document("scheduler_metadata", update_data)

            logger.info(f"✅ 任务 {job_id} 元数据已更新")
            return True
        except Exception as e:
            logger.error(f"❌ 更新任务 {job_id} 元数据失败: {e}")
            return False

    async def _dual_write_scheduler_document(
        self, collection: str, document: Dict[str, Any]
    ) -> None:
        result = await dual_write_hot_document(collection, document)
        if result.status == "failed":
            logger.warning(
                "⚠️ 调度器 PostgreSQL 双写失败: collection=%s reason=%s",
                collection,
                result.reason,
            )
