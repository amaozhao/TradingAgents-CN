# ruff: noqa: F401,F403,F405,F821
@router.get("/tasks/{task_id}/details", response_model=AnalysisLooseObjectResponse)
async def get_task_details(
    task_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service),
):
    """获取任务详情（使用不同的路径避免冲突）"""
    t = await svc.get_task(task_id)
    if not t or t.get("user") != user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    return t


# ==================== 僵尸任务管理 ====================


async def _delete_analysis_task_structured_rows(task_id: str) -> int:
    init_postgres = getattr(importlib.import_module("app.core.session"), "init_postgres")
    get_session_factory = getattr(
        importlib.import_module("app.core.session"), "get_session_factory"
    )
    text = getattr(importlib.import_module("sqlalchemy"), "text")

    await init_postgres()
    async with get_session_factory()() as session:
        structured_result = await session.execute(
            text("delete from analysis_tasks where task_id = :task_id"),
            {"task_id": task_id},
        )
        document_result = await session.execute(
            text(
                "delete from postgres_documents "
                "where collection = 'analysis_tasks' "
                "and payload->>'task_id' = :task_id"
            ),
            {"task_id": task_id},
        )
        await session.commit()
        return int(structured_result.rowcount or 0) + int(
            document_result.rowcount or 0
        )


@router.get("/admin/zombie-tasks", response_model=ZombieTasksResponse)
async def get_zombie_tasks(
    max_running_hours: int = Query(
        default=2, ge=1, le=72, description="最大运行时长（小时）"
    ),
    user: dict = Depends(get_current_user),
):
    """获取僵尸任务列表（仅管理员）

    僵尸任务：长时间处于 processing/running/pending 状态的任务
    """
    # 检查管理员权限
    if user.get("username") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    try:
        svc = get_simple_analysis_service()
        zombie_tasks = await svc.get_zombie_tasks(max_running_hours)

        return {
            "success": True,
            "data": zombie_tasks,
            "total": len(zombie_tasks),
            "max_running_hours": max_running_hours,
        }
    except Exception as e:
        logger.error(f"❌ 获取僵尸任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取僵尸任务失败: {str(e)}")


@router.post("/admin/cleanup-zombie-tasks", response_model=ApiResponse)
async def cleanup_zombie_tasks(
    max_running_hours: int = Query(
        default=2, ge=1, le=72, description="最大运行时长（小时）"
    ),
    user: dict = Depends(get_current_user),
):
    """清理僵尸任务（仅管理员）

    将长时间处于 processing/running/pending 状态的任务标记为失败
    """
    # 检查管理员权限
    if user.get("username") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    try:
        svc = get_simple_analysis_service()
        result = await svc.cleanup_zombie_tasks(max_running_hours)

        return {
            "success": True,
            "data": result,
            "message": f"已清理 {result.get('total_cleaned', 0)} 个僵尸任务",
        }
    except Exception as e:
        logger.error(f"❌ 清理僵尸任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理僵尸任务失败: {str(e)}")


@router.post("/tasks/{task_id}/mark-failed", response_model=AnalysisOperationResponse)
async def mark_task_as_failed(task_id: str, user: dict = Depends(get_current_user)):
    """将指定任务标记为失败

    用于手动清理卡住的任务
    """
    try:
        svc = get_simple_analysis_service()

        # 更新内存中的任务状态
        TaskStatus = getattr(
            importlib.import_module("app.services.memory"), "TaskStatus"
        )
        await svc.memory_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus.FAILED,
            message="手动标记为失败",
            error_message="用户手动标记为失败",
        )

        # 更新 PostgreSQL 中的任务状态
        db = get_postgres_db()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        update_data = {
            "task_id": task_id,
            "status": "failed",
            "last_error": "用户手动标记为失败",
            "completed_at": now,
            "updated_at": now,
        }

        result = await db.analysis_tasks.update_one(
            {"task_id": task_id}, {"$set": update_data}
        )
        if result.modified_count > 0:
            await dual_write_hot_document("analysis_tasks", update_data)

        if result.modified_count > 0:
            logger.info(f"✅ 任务 {task_id} 已标记为失败")
            return {"success": True, "message": "任务已标记为失败"}
        else:
            logger.warning(f"⚠️ 任务 {task_id} 未找到或已是失败状态")
            return {"success": True, "message": "任务未找到或已是失败状态"}
    except Exception as e:
        logger.error(f"❌ 标记任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"标记任务失败: {str(e)}")


@router.delete("/tasks/{task_id}", response_model=AnalysisOperationResponse)
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    """删除指定任务

    从内存和数据库中删除任务记录
    """
    try:
        svc = get_simple_analysis_service()

        # 从内存中删除任务
        await svc.memory_manager.remove_task(task_id)

        # 从 PostgreSQL 中删除任务
        db = get_postgres_db()
        result = await db.analysis_tasks.delete_one({"task_id": task_id})

        structured_deleted = await _delete_analysis_task_structured_rows(task_id)

        if result.deleted_count > 0 or structured_deleted > 0:
            logger.info(
                "✅ 任务 %s 已删除: document_store=%s structured=%s",
                task_id,
                result.deleted_count,
                structured_deleted,
            )
            return {"success": True, "message": "任务已删除"}
        else:
            logger.warning(f"⚠️ 任务 {task_id} 未找到")
            return {"success": True, "message": "任务未找到"}
    except Exception as e:
        logger.error(f"❌ 删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")
