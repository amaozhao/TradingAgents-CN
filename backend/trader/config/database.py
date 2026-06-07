#!/usr/bin/env python3
"""
数据库配置管理模块
统一管理 PostgreSQL 和 Redis 的连接配置
"""

from typing import Any, Dict

from app.core.config import settings


class DatabaseConfig:
    """数据库配置管理类"""

    @staticmethod
    def get_postgres_config() -> Dict[str, Any]:
        """
        获取 PostgreSQL document store 兼容配置

        Returns:
            Dict[str, Any]: PostgreSQL配置字典

        Raises:
            ValueError: 当必要的配置未设置时
        """
        database = settings.POSTGRES_DB
        if not database:
            raise ValueError("PostgreSQL数据库未配置。请设置环境变量 POSTGRES_DB")

        return {
            "database": database,
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
        }

    @staticmethod
    def get_redis_config() -> Dict[str, Any]:
        """
        获取Redis配置

        Returns:
            Dict[str, Any]: Redis配置字典

        Raises:
            ValueError: 当必要的配置未设置时
        """
        # 优先使用连接字符串
        connection_string = settings.REDIS_CONNECTION_STRING
        if connection_string:
            return {
                "connection_string": connection_string,
                "database": settings.REDIS_DATABASE,
            }

        # 使用分离的配置参数
        host = settings.REDIS_HOST
        port = settings.REDIS_PORT

        if not host or not port:
            raise ValueError(
                "Redis连接配置未完整设置。请设置以下环境变量之一：\n"
                "1. REDIS_CONNECTION_STRING=redis://localhost:6379/0\n"
                "2. REDIS_HOST + REDIS_PORT (例如: REDIS_HOST=localhost, REDIS_PORT=6379)"
            )

        return {
            "host": host,
            "port": int(port),
            "password": settings.REDIS_PASSWORD or None,
            "database": settings.REDIS_DATABASE,
        }

    @staticmethod
    def validate_config() -> Dict[str, bool]:
        """
        验证数据库配置是否完整

        Returns:
            Dict[str, bool]: 验证结果
        """
        result = {"postgres_valid": False, "redis_valid": False}

        try:
            DatabaseConfig.get_postgres_config()
            result["postgres_valid"] = True
        except ValueError:
            pass

        try:
            DatabaseConfig.get_redis_config()
            result["redis_valid"] = True
        except ValueError:
            pass

        return result

    @staticmethod
    def get_config_status() -> str:
        """
        获取配置状态的友好描述

        Returns:
            str: 配置状态描述
        """
        validation = DatabaseConfig.validate_config()

        if validation["postgres_valid"] and validation["redis_valid"]:
            return "✅ 所有数据库配置正常"
        elif validation["postgres_valid"]:
            return "⚠️ PostgreSQL配置正常，Redis配置缺失"
        elif validation["redis_valid"]:
            return "⚠️ Redis配置正常，PostgreSQL配置缺失"
        else:
            return "❌ 数据库配置缺失，请检查环境变量"
