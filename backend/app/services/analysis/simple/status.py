# ruff: noqa: F403,F405
from .common import *


class AnalysisStatusMixin:
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        logger.info(f"🔍 查询任务状态: {task_id}")
        logger.info(f"🔍 当前服务实例ID: {id(self)}")
        logger.info(f"🔍 内存管理器实例ID: {id(self.memory_manager)}")

        # 强制使用全局内存管理器实例（临时解决方案）
        global_memory_manager = get_memory_state_manager()
        logger.info(f"🔍 全局内存管理器实例ID: {id(global_memory_manager)}")

        # 获取统计信息
        stats = await global_memory_manager.get_statistics()
        logger.info(f"📊 内存中任务统计: {stats}")

        result = await global_memory_manager.get_task_dict(task_id)
        if result:
            logger.info(f"✅ 找到任务: {task_id} - 状态: {result.get('status')}")

            # 🔍 调试：检查从内存获取的result_data
            result_data = result.get("result_data")
            logger.debug(f"🔍 [GET_STATUS] result_data存在: {bool(result_data)}")
            if result_data:
                logger.debug(
                    f"🔍 [GET_STATUS] result_data键: {list(result_data.keys())}"
                )
                logger.debug(
                    f"🔍 [GET_STATUS] result_data中有decision: {bool(result_data.get('decision'))}"
                )
                if result_data.get("decision"):
                    logger.debug(
                        f"🔍 [GET_STATUS] decision内容: {result_data['decision']}"
                    )
            else:
                logger.debug(
                    "🔍 [GET_STATUS] result_data为空或不存在（任务运行中，这是正常的）"
                )

            # 优先从Redis获取详细进度信息
            redis_progress = get_progress_by_id(task_id)
            if redis_progress:
                logger.info(f"📊 [Redis进度] 获取到详细进度: {task_id}")

                # 从 steps 数组中提取当前步骤的名称和描述
                current_step_index = redis_progress.get("current_step", 0)
                steps = redis_progress.get("steps", [])
                current_step_name = redis_progress.get("current_step_name", "")
                current_step_description = redis_progress.get(
                    "current_step_description", ""
                )

                # 如果 Redis 中的名称/描述为空，从 steps 数组中提取
                if (
                    not current_step_name
                    and steps
                    and 0 <= current_step_index < len(steps)
                ):
                    current_step_info = steps[current_step_index]
                    current_step_name = current_step_info.get("name", "")
                    current_step_description = current_step_info.get("description", "")
                    logger.info(
                        f"📋 从steps数组提取当前步骤信息: index={current_step_index}, name={current_step_name}"
                    )

                # 合并Redis进度数据
                result.update(
                    {
                        "progress": redis_progress.get(
                            "progress_percentage", result.get("progress", 0)
                        ),
                        "current_step": current_step_index,  # 使用索引而不是名称
                        "current_step_name": current_step_name,  # 步骤名称
                        "current_step_description": current_step_description,  # 步骤描述
                        "message": redis_progress.get(
                            "last_message", result.get("message", "")
                        ),
                        "elapsed_time": redis_progress.get("elapsed_time", 0),
                        "remaining_time": redis_progress.get("remaining_time", 0),
                        "estimated_total_time": redis_progress.get(
                            "estimated_total_time",
                            result.get("estimated_duration", 300),
                        ),  # 🔧 修复：使用Redis中的预估总时长
                        "steps": steps,
                        "start_time": result.get("start_time"),  # 保持原有格式
                        "last_update": redis_progress.get(
                            "last_update", result.get("start_time")
                        ),
                    }
                )
            else:
                # 如果Redis中没有，尝试从内存中的进度跟踪器获取
                if task_id in self._trackers:
                    tracker = self._trackers[task_id]
                    progress_data = tracker.to_dict()

                    # 合并进度跟踪器的详细信息
                    result.update(
                        {
                            "progress": progress_data["progress"],
                            "current_step": progress_data["current_step"],
                            "message": progress_data["message"],
                            "elapsed_time": progress_data["elapsed_time"],
                            "remaining_time": progress_data["remaining_time"],
                            "estimated_total_time": progress_data.get(
                                "estimated_total_time", 0
                            ),
                            "steps": progress_data["steps"],
                            "start_time": progress_data["start_time"],
                            "last_update": progress_data["last_update"],
                        }
                    )
                    logger.info(f"📊 合并内存进度跟踪器数据: {task_id}")
                else:
                    logger.info(f"⚠️ 未找到进度信息: {task_id}")
        else:
            logger.warning(f"❌ 未找到任务: {task_id}")

        return result

    async def list_all_tasks(
        self, status: Optional[str] = None, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取所有任务列表（不限用户）
        - 合并内存和 PostgreSQL 数据
        - 按开始时间倒序排列
        """
        try:
            task_status = None
            if status:
                try:
                    status_mapping = {
                        "processing": "running",
                        "pending": "pending",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled",
                    }
                    mapped_status = status_mapping.get(status, status)
                    task_status = TaskStatus(mapped_status)
                except ValueError:
                    logger.warning(f"⚠️ [Tasks] 无效的状态值: {status}")
                    task_status = None

            # 1) 从内存读取所有任务
            logger.info(
                f"📋 [Tasks] 准备从内存读取所有任务: status={status}, limit={limit}, offset={offset}"
            )
            tasks_in_mem = await self.memory_manager.list_all_tasks(
                status=task_status, limit=limit * 2, offset=0
            )
            logger.info(f"📋 [Tasks] 内存返回数量: {len(tasks_in_mem)}")

            # 2) 从 PostgreSQL 读取任务
            db = get_postgres_db()
            collection = db["analysis_tasks"]

            query = {}
            if task_status:
                query["status"] = task_status.value

            count = await collection.count_documents(query)
            logger.info(f"📋 [Tasks] PostgreSQL 任务总数: {count}")

            cursor = collection.find(query).sort("start_time", -1).limit(limit * 2)
            tasks_from_db = []
            async for doc in cursor:
                doc.pop("_id", None)
                tasks_from_db.append(doc)

            logger.info(f"📋 [Tasks] PostgreSQL 返回数量: {len(tasks_from_db)}")

            # 3) 合并任务（内存优先）
            task_dict = {}

            # 先添加 PostgreSQL 中的任务
            for task in tasks_from_db:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 再添加内存中的任务（覆盖 PostgreSQL 中的同名任务）
            for task in tasks_in_mem:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 转换为列表并按时间排序
            merged_tasks = list(task_dict.values())
            merged_tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)

            # 分页
            results = merged_tasks[offset : offset + limit]

            # 为结果补齐股票名称
            results = self._enrich_stock_names(results)
            logger.info(
                f"📋 [Tasks] 合并后返回数量: {len(results)} (内存: {len(tasks_in_mem)}, PostgreSQL: {count})"
            )
            return results
        except Exception as outer_e:
            logger.error(f"❌ list_all_tasks 外层异常: {outer_e}", exc_info=True)
            return []

    async def _list_user_tasks_from_postgres_tables(
        self,
        *,
        user_id: str,
        status: Optional[str],
        limit: int,
        offset: int,
    ) -> Optional[List[Dict[str, Any]]]:
        if not settings.POSTGRES_READ_ENABLED:
            return None
        try:
            list_user_analysis_tasks = getattr(
                importlib.import_module("app.db.analysis"), "list_user_analysis_tasks"
            )
            get_session_factory = getattr(
                importlib.import_module("app.db.session"), "get_session_factory"
            )

            async with get_session_factory()() as session:
                documents = await list_user_analysis_tasks(
                    session,
                    user_id,
                    status=status,
                    limit=limit,
                    offset=offset,
                )
            return [
                self._analysis_task_document_to_history_item(doc) for doc in documents
            ]
        except Exception as e:
            logger.warning("PostgreSQL结构化任务表查询失败，回退文档存储: %s", e)
            return None

    async def _list_user_tasks_from_postgres_documents(
        self,
        *,
        user_id: str,
        task_status: Optional[TaskStatus],
        limit: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        db = get_postgres_db()

        uid_candidates: List[Any] = [user_id]

        if str(user_id) == "admin":
            try:
                DocumentId = getattr(
                    importlib.import_module("app.db.ids"), "DocumentId"
                )
                admin_document_id_str = "507f1f77bcf86cd799439011"
                uid_candidates.append(DocumentId(admin_document_id_str))
                uid_candidates.append(admin_document_id_str)
                logger.info(
                    f"📋 [Tasks] admin用户查询，候选ID: ['admin', DocumentId('{admin_document_id_str}'), '{admin_document_id_str}']"
                )
            except Exception as e:
                logger.warning(f"⚠️ [Tasks] admin用户DocumentId创建失败: {e}")
        else:
            try:
                DocumentId = getattr(
                    importlib.import_module("app.db.ids"), "DocumentId"
                )
                uid_candidates.append(DocumentId(user_id))
                logger.debug(f"📋 [Tasks] 用户ID已转换为DocumentId: {user_id}")
            except Exception as conv_err:
                logger.warning(
                    f"⚠️ [Tasks] 用户ID转换DocumentId失败，按字符串匹配: {conv_err}"
                )

        base_condition = {"$in": uid_candidates}
        query: Dict[str, Any] = {
            "$or": [{"user_id": base_condition}, {"user": base_condition}]
        }

        if task_status:
            query["status"] = task_status.value
            logger.info(f"📋 [Tasks] 添加状态过滤: {task_status.value}")

        logger.info(f"📋 [Tasks] PostgreSQL 查询条件: {query}")
        cursor = db.analysis_tasks.find(query).sort("created_at", -1).limit(limit * 2)
        tasks = []
        count = 0
        async for doc in cursor:
            count += 1
            tasks.append(self._analysis_task_document_to_history_item(doc))
        return tasks, count

    def _analysis_task_document_to_history_item(
        self, doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        user_field_val = doc.get("user_id", doc.get("user"))
        stock_code_value = (
            doc.get("symbol") or doc.get("stock_code") or doc.get("stock_symbol")
        )
        item = {
            "task_id": doc.get("task_id"),
            "user_id": str(user_field_val) if user_field_val is not None else None,
            "symbol": stock_code_value,
            "stock_code": stock_code_value,
            "stock_symbol": stock_code_value,
            "stock_name": doc.get("stock_name"),
            "status": str(doc.get("status", "pending")),
            "progress": int(doc.get("progress", 0) or 0),
            "message": doc.get("message", ""),
            "current_step": doc.get("current_step", ""),
            "start_time": doc.get("started_at") or doc.get("created_at"),
            "end_time": doc.get("completed_at"),
            "parameters": doc.get("parameters", {}),
            "execution_time": doc.get("execution_time"),
            "tokens_used": doc.get("tokens_used"),
            "result_data": doc.get("result"),
        }
        for key in ("start_time", "end_time"):
            if item.get(key) and hasattr(item[key], "isoformat"):
                dt = item[key]
                if dt.tzinfo is None:
                    timezone = getattr(importlib.import_module("datetime"), "timezone")
                    timedelta = getattr(
                        importlib.import_module("datetime"), "timedelta"
                    )
                    china_tz = timezone(timedelta(hours=8))
                    dt = dt.replace(tzinfo=china_tz)
                item[key] = dt.isoformat()
        return item

    async def list_user_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取用户任务列表
        - 对于 processing 状态：优先从内存读取（实时进度）
        - 对于 completed/failed/all 状态：合并内存和 PostgreSQL 数据
        """
        try:
            task_status = None
            if status:
                try:
                    # 前端传递的是 "processing"，但 TaskStatus 使用的是 "running"
                    # 需要做映射转换
                    status_mapping = {
                        "processing": "running",  # 前端使用 processing，内存使用 running
                        "pending": "pending",
                        "completed": "completed",
                        "failed": "failed",
                        "cancelled": "cancelled",
                    }
                    mapped_status = status_mapping.get(status, status)
                    task_status = TaskStatus(mapped_status)
                except ValueError:
                    logger.warning(f"⚠️ [Tasks] 无效的状态值: {status}")
                    task_status = None

            # 1) 从内存读取任务
            logger.info(
                f"📋 [Tasks] 准备从内存读取任务: user_id={user_id}, status={status} (mapped to {task_status}), limit={limit}, offset={offset}"
            )
            tasks_in_mem = await self.memory_manager.list_user_tasks(
                user_id=user_id,
                status=task_status,
                limit=limit * 2,  # 多读一些，后面合并去重
                offset=0,  # 内存中的任务不多，全部读取
            )
            logger.info(f"📋 [Tasks] 内存返回数量: {len(tasks_in_mem)}")

            # 2) 🔧 对于 processing/running 状态，需要合并 PostgreSQL 数据以获取最新进度
            # 因为 graph_progress_callback 可能直接更新了 PostgreSQL，而内存数据可能是旧的

            # 3) 从 PostgreSQL 读取历史任务（用于合并或兜底）
            logger.info("📋 [Tasks] 从 PostgreSQL 读取历史任务")
            postgres_tasks: List[Dict[str, Any]] = []
            count = 0
            try:
                table_tasks = await self._list_user_tasks_from_postgres_tables(
                    user_id=user_id,
                    status=task_status.value if task_status else None,
                    limit=limit * 2,
                    offset=0,
                )
                if table_tasks:
                    postgres_tasks = table_tasks
                    count = len(postgres_tasks)
                    logger.info(f"📋 [Tasks] PostgreSQL结构化表返回数量: {count}")
                else:
                    (
                        postgres_tasks,
                        count,
                    ) = await self._list_user_tasks_from_postgres_documents(
                        user_id=user_id,
                        task_status=task_status,
                        limit=limit,
                    )

                logger.info(f"📋 [Tasks] PostgreSQL 返回数量: {count}")
            except Exception as postgres_e:
                logger.error(
                    f"❌ PostgreSQL 查询任务列表失败: {postgres_e}", exc_info=True
                )
                # PostgreSQL 查询失败，继续使用内存数据

            # 4) 合并内存和 PostgreSQL 数据，去重
            # 🔧 对于 processing/running 状态，优先使用 PostgreSQL 中的进度数据
            # 因为 graph_progress_callback 直接更新 PostgreSQL，而内存数据可能是旧的
            task_dict = {}

            # 先添加内存中的任务
            for task in tasks_in_mem:
                task_id = task.get("task_id")
                if task_id:
                    task_dict[task_id] = task

            # 再添加 PostgreSQL 中的任务
            # 对于 processing/running 状态，使用 PostgreSQL 中的进度数据（更新）
            # 对于其他状态，如果内存中已有，则跳过（内存优先）
            for task in postgres_tasks:
                task_id = task.get("task_id")
                if not task_id:
                    continue

                # 如果内存中已有这个任务
                if task_id in task_dict:
                    mem_task = task_dict[task_id]
                    postgres_task = task

                    # 如果是 processing/running 状态，使用 PostgreSQL 中的进度数据
                    if postgres_task.get("status") in ["processing", "running"]:
                        # 保留内存中的基本信息，但更新进度相关字段
                        mem_task["progress"] = postgres_task.get(
                            "progress", mem_task.get("progress", 0)
                        )
                        mem_task["message"] = postgres_task.get(
                            "message", mem_task.get("message", "")
                        )
                        mem_task["current_step"] = postgres_task.get(
                            "current_step", mem_task.get("current_step", "")
                        )
                        logger.debug(
                            f"🔄 [Tasks] 更新任务进度: {task_id}, progress={mem_task['progress']}%"
                        )
                else:
                    # 内存中没有，直接添加 PostgreSQL 中的任务
                    task_dict[task_id] = task

            # 转换为列表并按时间排序
            merged_tasks = list(task_dict.values())
            merged_tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)

            # 分页
            results = merged_tasks[offset : offset + limit]

            # 🔥 统一处理时区信息（确保所有时间字段都有时区标识）
            timezone = getattr(importlib.import_module("datetime"), "timezone")
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")
            china_tz = timezone(timedelta(hours=8))

            for task in results:
                for time_field in (
                    "start_time",
                    "end_time",
                    "created_at",
                    "started_at",
                    "completed_at",
                ):
                    value = task.get(time_field)
                    if value:
                        # 如果是 datetime 对象
                        if hasattr(value, "isoformat"):
                            # 如果是 naive datetime，添加时区信息
                            if value.tzinfo is None:
                                value = value.replace(tzinfo=china_tz)
                            task[time_field] = value.isoformat()
                        # 如果是字符串且没有时区标识，添加时区标识
                        elif (
                            isinstance(value, str)
                            and value
                            and not value.endswith(("Z", "+08:00", "+00:00"))
                        ):
                            # 检查是否是 ISO 格式的时间字符串
                            if "T" in value or " " in value:
                                task[time_field] = value.replace(" ", "T") + "+08:00"

            # 为结果补齐股票名称
            results = self._enrich_stock_names(results)
            logger.info(
                f"📋 [Tasks] 合并后返回数量: {len(results)} (内存: {len(tasks_in_mem)}, PostgreSQL: {count})"
            )
            return results
        except Exception as outer_e:
            logger.error(f"❌ list_user_tasks 外层异常: {outer_e}", exc_info=True)
            return []

    async def cleanup_zombie_tasks(self, max_running_hours: int = 2) -> Dict[str, Any]:
        """清理僵尸任务（长时间处于 processing/running 状态的任务）

        Args:
            max_running_hours: 最大运行时长（小时），超过此时长的任务将被标记为失败

        Returns:
            清理结果统计
        """
        try:
            # 1) 清理内存中的僵尸任务
            memory_cleaned = await self.memory_manager.cleanup_zombie_tasks(
                max_running_hours
            )

            # 2) 清理 PostgreSQL 中的僵尸任务
            db = get_postgres_db()
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")
            cutoff_time = datetime.utcnow() - timedelta(hours=max_running_hours)

            # 查找长时间处于 processing 状态的任务
            zombie_filter = {
                "status": {"$in": ["processing", "running", "pending"]},
                "$or": [
                    {"started_at": {"$lt": cutoff_time}},
                    {"created_at": {"$lt": cutoff_time, "started_at": None}},
                ],
            }

            # 更新为失败状态
            update_result = await db.analysis_tasks.update_many(
                zombie_filter,
                {
                    "$set": {
                        "status": "failed",
                        "last_error": f"任务超时（运行时间超过 {max_running_hours} 小时）",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            postgres_cleaned = update_result.modified_count

            logger.info(
                f"🧹 僵尸任务清理完成: 内存={memory_cleaned}, PostgreSQL={postgres_cleaned}"
            )

            return {
                "success": True,
                "memory_cleaned": memory_cleaned,
                "postgres_cleaned": postgres_cleaned,
                "total_cleaned": memory_cleaned + postgres_cleaned,
                "max_running_hours": max_running_hours,
            }

        except Exception as e:
            logger.error(f"❌ 清理僵尸任务失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "memory_cleaned": 0,
                "postgres_cleaned": 0,
                "total_cleaned": 0,
            }

    async def get_zombie_tasks(
        self, max_running_hours: int = 2
    ) -> List[Dict[str, Any]]:
        """获取僵尸任务列表（不执行清理，仅查询）

        Args:
            max_running_hours: 最大运行时长（小时）

        Returns:
            僵尸任务列表
        """
        try:
            db = get_postgres_db()
            timedelta = getattr(importlib.import_module("datetime"), "timedelta")
            cutoff_time = datetime.utcnow() - timedelta(hours=max_running_hours)

            # 查找长时间处于 processing 状态的任务
            zombie_filter = {
                "status": {"$in": ["processing", "running", "pending"]},
                "$or": [
                    {"started_at": {"$lt": cutoff_time}},
                    {"created_at": {"$lt": cutoff_time, "started_at": None}},
                ],
            }

            cursor = db.analysis_tasks.find(zombie_filter).sort("created_at", -1)
            zombie_tasks = []

            async for doc in cursor:
                task = {
                    "task_id": doc.get("task_id"),
                    "user_id": str(doc.get("user_id", doc.get("user"))),
                    "stock_code": doc.get("stock_code"),
                    "stock_name": doc.get("stock_name"),
                    "status": doc.get("status"),
                    "created_at": cast(Any, doc.get("created_at")).isoformat()
                    if doc.get("created_at")
                    else None,
                    "started_at": cast(Any, doc.get("started_at")).isoformat()
                    if doc.get("started_at")
                    else None,
                    "running_hours": None,
                }

                # 计算运行时长
                start_time = doc.get("started_at") or doc.get("created_at")
                if start_time:
                    running_seconds = (datetime.utcnow() - start_time).total_seconds()
                    task["running_hours"] = round(running_seconds / 3600, 2)

                zombie_tasks.append(task)

            logger.info(f"📋 查询到 {len(zombie_tasks)} 个僵尸任务")
            return zombie_tasks

        except Exception as e:
            logger.error(f"❌ 查询僵尸任务失败: {e}", exc_info=True)
            return []

    async def _update_task_status(
        self,
        task_id: str,
        status: AnalysisStatus,
        progress: int,
        error_message: Optional[str] = None,
    ):
        """更新任务状态"""
        try:
            db = get_postgres_db()
            update_data = {
                "status": status,
                "progress": progress,
                "updated_at": datetime.utcnow(),
            }

            if status == AnalysisStatus.PROCESSING and progress == 10:
                update_data["started_at"] = datetime.utcnow()
            elif status == AnalysisStatus.COMPLETED:
                update_data["completed_at"] = datetime.utcnow()
            elif status == AnalysisStatus.FAILED:
                update_data["last_error"] = error_message
                update_data["completed_at"] = datetime.utcnow()

            await db.analysis_tasks.update_one(
                {"task_id": task_id}, {"$set": update_data}
            )

            logger.debug(f"📊 任务状态已更新: {task_id} -> {status} ({progress}%)")

        except Exception as e:
            logger.error(f"❌ 更新任务状态失败: {task_id} - {e}")
