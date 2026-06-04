"""
Cleanup routines extracted from DatabaseService.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.database import get_postgres_db
from app.db.dual import dual_write_hot_documents


async def _dual_write_tombstones(
    collection: str, documents: list[dict], deleted_at: datetime
) -> None:
    if not documents:
        return
    result = await dual_write_hot_documents(
        collection,
        [
            {**document, "deleted": True, "updated_at": deleted_at}
            for document in documents
        ],
    )
    if result.status == "failed":
        # Cleanup should not fail only because the staged PostgreSQL mirror is temporarily unavailable.
        return


async def cleanup_old_data(days: int) -> Dict[str, Any]:
    db = get_postgres_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    analysis_tasks_to_delete = await db.analysis_tasks.find(
        {
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": ["completed", "failed"]},
        }
    ).to_list(length=None)
    res = await db.analysis_tasks.delete_many(
        {
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": ["completed", "failed"]},
        }
    )
    if res.deleted_count:
        await _dual_write_tombstones(
            "analysis_tasks", analysis_tasks_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis_tasks: {res.deleted_count}")

    user_sessions_to_delete = await db.user_sessions.find(
        {"created_at": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.user_sessions.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones(
            "user_sessions", user_sessions_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"user_sessions: {res.deleted_count}")

    login_attempts_to_delete = await db.login_attempts.find(
        {"timestamp": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.login_attempts.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones(
            "login_attempts", login_attempts_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"login_attempts: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }


async def cleanup_analysis(days: int) -> Dict[str, Any]:
    db = get_postgres_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    analysis_tasks_to_delete = await db.analysis_tasks.find(
        {
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": ["completed", "failed"]},
        }
    ).to_list(length=None)
    res = await db.analysis_tasks.delete_many(
        {
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": ["completed", "failed"]},
        }
    )
    if res.deleted_count:
        await _dual_write_tombstones(
            "analysis_tasks", analysis_tasks_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis_tasks: {res.deleted_count}")

    analysis_to_delete = await db.analysis.find(
        {"created_at": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.analysis.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones("analysis", analysis_to_delete, datetime.utcnow())
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }


async def cleanup_operations(days: int) -> Dict[str, Any]:
    db = get_postgres_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    user_sessions_to_delete = await db.user_sessions.find(
        {"created_at": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.user_sessions.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones(
            "user_sessions", user_sessions_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"user_sessions: {res.deleted_count}")

    login_attempts_to_delete = await db.login_attempts.find(
        {"timestamp": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.login_attempts.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones(
            "login_attempts", login_attempts_to_delete, datetime.utcnow()
        )
        deleted_count += res.deleted_count
        cleaned_collections.append(f"login_attempts: {res.deleted_count}")

    old_operations = await db.operations.find(
        {"timestamp": {"$lt": cutoff_date}}
    ).to_list(length=None)
    res = await db.operations.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        await _dual_write_tombstones("operations", old_operations, datetime.utcnow())
        deleted_count += res.deleted_count
        cleaned_collections.append(f"operations: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }
