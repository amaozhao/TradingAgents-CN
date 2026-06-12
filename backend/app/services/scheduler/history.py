from .common import (
    Any,
    Dict,
    List,
    Optional,
    get_utc8_now,
    importlib,
    logger,
)


class SchedulerHistoryMixin:
    async def get_job_history(
        self, job_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取任务执行历史

        Args:
            job_id: 任务ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            执行历史记录
        """
        try:
            db = self._get_db()
            cursor = (
                db.scheduler_history.find({"job_id": job_id})
                .sort("timestamp", -1)
                .skip(offset)
                .limit(limit)
            )

            history = []
            async for doc in cursor:
                doc.pop("_id", None)
                history.append(doc)

            return history
        except Exception as e:
            logger.error(f"❌ 获取任务 {job_id} 执行历史失败: {e}")
            return []

    async def count_job_history(self, job_id: str) -> int:
        """
        统计任务执行历史数量

        Args:
            job_id: 任务ID

        Returns:
            历史记录数量
        """
        try:
            db = self._get_db()
            count = await db.scheduler_history.count_documents({"job_id": job_id})
            return count
        except Exception as e:
            logger.error(f"❌ 统计任务 {job_id} 执行历史失败: {e}")
            return 0

    async def get_all_history(
        self,
        limit: int = 50,
        offset: int = 0,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取所有任务执行历史

        Args:
            limit: 返回数量限制
            offset: 偏移量
            job_id: 任务ID过滤
            status: 状态过滤

        Returns:
            执行历史记录
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            cursor = (
                db.scheduler_history.find(query)
                .sort("timestamp", -1)
                .skip(offset)
                .limit(limit)
            )

            history = []
            async for doc in cursor:
                doc.pop("_id", None)
                history.append(doc)

            return history
        except Exception as e:
            logger.error(f"❌ 获取执行历史失败: {e}")
            return []

    async def count_all_history(
        self, job_id: Optional[str] = None, status: Optional[str] = None
    ) -> int:
        """
        统计所有任务执行历史数量

        Args:
            job_id: 任务ID过滤
            status: 状态过滤

        Returns:
            历史记录数量
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            count = await db.scheduler_history.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"❌ 统计执行历史失败: {e}")
            return 0

    async def get_job_executions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        is_manual: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        获取任务执行历史

        Args:
            job_id: 任务ID（可选，不指定则返回所有任务）
            status: 状态过滤（success/failed/missed/running）
            is_manual: 是否手动触发（True=手动，False=自动，None=全部）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            执行历史列表
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            # 处理 is_manual 过滤
            if is_manual is not None:
                if is_manual:
                    # 手动触发：is_manual 必须为 true
                    query["is_manual"] = True
                else:
                    # 自动触发：is_manual 字段不存在或为 false
                    # 使用 $ne (not equal) 来排除 is_manual=true 的记录
                    query["is_manual"] = {"$ne": True}

            cursor = (
                db.scheduler_executions.find(query)
                .sort("timestamp", -1)
                .skip(offset)
                .limit(limit)
            )

            executions = []
            async for doc in cursor:
                # 转换 _id 为字符串
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

                # 格式化时间（document store 存储的是 naive datetime，表示本地时间）
                # 直接序列化为 ISO 格式字符串，前端会自动添加 +08:00 后缀
                for time_field in ["scheduled_time", "timestamp", "updated_at"]:
                    if doc.get(time_field):
                        dt = doc[time_field]
                        # 如果是 datetime 对象，转换为 ISO 格式字符串
                        if hasattr(dt, "isoformat"):
                            doc[time_field] = dt.isoformat()

                executions.append(doc)

            return executions
        except Exception as e:
            logger.error(f"❌ 获取任务执行历史失败: {e}")
            return []

    async def count_job_executions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        is_manual: Optional[bool] = None,
    ) -> int:
        """
        统计任务执行历史数量

        Args:
            job_id: 任务ID（可选）
            status: 状态过滤（可选）
            is_manual: 是否手动触发（可选）

        Returns:
            执行历史数量
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            # 处理 is_manual 过滤
            if is_manual is not None:
                if is_manual:
                    # 手动触发：is_manual 必须为 true
                    query["is_manual"] = True
                else:
                    # 自动触发：is_manual 字段不存在或为 false
                    query["is_manual"] = {"$ne": True}

            count = await db.scheduler_executions.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"❌ 统计任务执行历史失败: {e}")
            return 0

    async def cancel_job_execution(self, execution_id: str) -> bool:
        """
        取消/终止任务执行

        对于正在执行的任务，设置取消标记；
        对于已经退出但数据库中仍为running的任务，直接标记为failed

        Args:
            execution_id: 执行记录ID（PostgreSQL _id）

        Returns:
            是否成功
        """
        try:
            DocumentId = getattr(importlib.import_module("app.db.ids"), "DocumentId")
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one(
                {"_id": DocumentId(execution_id)}
            )
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            if execution.get("status") != "running":
                logger.warning(
                    f"⚠️ 执行记录状态不是running: {execution_id} (status={execution.get('status')})"
                )
                return False

            # 设置取消标记
            await db.scheduler_executions.update_one(
                {"_id": DocumentId(execution_id)},
                {"$set": {"cancel_requested": True, "updated_at": get_utc8_now()}},
            )

            logger.info(
                f"✅ 已设置取消标记: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 取消任务执行失败: {e}")
            return False

    async def mark_execution_as_failed(
        self, execution_id: str, reason: str = "用户手动标记为失败"
    ) -> bool:
        """
        将执行记录标记为失败状态

        用于处理已经退出但数据库中仍为running的任务

        Args:
            execution_id: 执行记录ID（PostgreSQL _id）
            reason: 失败原因

        Returns:
            是否成功
        """
        try:
            DocumentId = getattr(importlib.import_module("app.db.ids"), "DocumentId")
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one(
                {"_id": DocumentId(execution_id)}
            )
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            # 更新为failed状态
            await db.scheduler_executions.update_one(
                {"_id": DocumentId(execution_id)},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": reason,
                        "updated_at": get_utc8_now(),
                    }
                },
            )

            logger.info(
                f"✅ 已标记为失败: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id}, reason={reason})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 标记执行记录为失败失败: {e}")
            return False

    async def delete_execution(self, execution_id: str) -> bool:
        """
        删除执行记录

        Args:
            execution_id: 执行记录ID（PostgreSQL _id）

        Returns:
            是否成功
        """
        try:
            DocumentId = getattr(importlib.import_module("app.db.ids"), "DocumentId")
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one(
                {"_id": DocumentId(execution_id)}
            )
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            # 不允许删除正在执行的任务
            if execution.get("status") == "running":
                logger.error(f"❌ 不能删除正在执行的任务: {execution_id}")
                return False

            # 删除记录
            result = await db.scheduler_executions.delete_one(
                {"_id": DocumentId(execution_id)}
            )

            if result.deleted_count > 0:
                logger.info(
                    f"✅ 已删除执行记录: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id})"
                )
                return True
            else:
                logger.error(f"❌ 删除执行记录失败: {execution_id}")
                return False

        except Exception as e:
            logger.error(f"❌ 删除执行记录失败: {e}")
            return False
