"""
Database status and connection checks, extracted from DatabaseService.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.core.config import settings
from app.core.database import get_postgres_db, get_redis_client


async def get_postgres_status() -> Dict[str, Any]:
    try:
        db = get_postgres_db()
        await db.command("ping")
        return {
            "connected": True,
            "type": "postgresql",
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "database": settings.POSTGRES_DB,
            "version": "PostgreSQL document store",
            "connected_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "type": "postgresql",
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "database": settings.POSTGRES_DB,
        }


async def get_redis_status() -> Dict[str, Any]:
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        info = await redis_client.info()
        return {
            "connected": True,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "database": settings.REDIS_DB,
            "version": info.get("redis_version", "Unknown"),
            "uptime": info.get("uptime_in_seconds", 0),
            "memory_used": info.get("used_memory", 0),
            "memory_peak": info.get("used_memory_peak", 0),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands": info.get("total_commands_processed", 0),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "database": settings.REDIS_DB,
        }


async def get_database_status() -> Dict[str, Any]:
    postgres_status = await get_postgres_status()
    redis_status = await get_redis_status()
    return {"postgres": postgres_status, "redis": redis_status}


async def test_postgres_connection() -> Dict[str, Any]:
    try:
        db = get_postgres_db()
        start = datetime.utcnow()
        await db.command("ping")
        took_ms = (datetime.utcnow() - start).total_seconds() * 1000
        return {
            "success": True,
            "response_time_ms": round(took_ms, 2),
            "message": "PostgreSQL连接正常",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": "PostgreSQL连接失败"}


async def test_redis_connection() -> Dict[str, Any]:
    try:
        redis_client = get_redis_client()
        start = datetime.utcnow()
        await redis_client.ping()
        took_ms = (datetime.utcnow() - start).total_seconds() * 1000
        return {
            "success": True,
            "response_time_ms": round(took_ms, 2),
            "message": "Redis连接正常",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Redis连接失败"}


async def test_connections() -> Dict[str, Any]:
    postgres = await test_postgres_connection()
    redis = await test_redis_connection()
    return {
        "postgres": postgres,
        "redis": redis,
        "overall": postgres["success"] and redis["success"],
    }
