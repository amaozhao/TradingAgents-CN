from pathlib import Path

from ..common import (
    Any,
    DatabaseConfig,
    Dict,
    importlib,
    logger,
    settings,
    time,
)


class DatabaseConfigTestMixin:
    async def test_database_config(self, db_config: DatabaseConfig) -> Dict[str, Any]:
        """测试数据库配置 - 真实连接测试"""
        start_time = time.time()
        try:
            db_type = (
                db_config.type.value
                if hasattr(db_config.type, "value")
                else str(db_config.type)
            )

            logger.info(f"🧪 测试数据库配置: {db_config.name} ({db_type})")
            logger.info(f"📍 连接地址: {db_config.host}:{db_config.port}")

            # 根据不同的数据库类型进行测试
            if db_type == "postgres":
                return {
                    "success": False,
                    "message": "PostgreSQL 已被 PostgreSQL 替代，后端不再测试或连接 PostgreSQL",
                    "response_time": time.time() - start_time,
                    "details": {
                        "type": db_type,
                        "replacement": "postgresql",
                    },
                }

            elif db_type == "redis":
                try:
                    aioredis = importlib.import_module("redis.asyncio")

                    # 🔥 优先使用环境变量中的完整 Redis 配置（包括host、密码）
                    host = db_config.host
                    port = db_config.port
                    password = db_config.password
                    database = db_config.database
                    used_env_config = False

                    # 检测是否在 Docker 环境中
                    is_docker = (
                        Path("/.dockerenv").exists() or settings.DOCKER_CONTAINER
                    )

                    # 如果配置中没有密码，尝试从环境变量获取完整配置
                    if not password:
                        env_host = settings.REDIS_HOST
                        env_port = settings.REDIS_PORT
                        env_password = settings.REDIS_PASSWORD

                        if env_password:
                            password = env_password
                            used_env_config = True

                            # 如果环境变量中有 host 配置，也使用它
                            if env_host:
                                host = env_host
                                # 🔥 Docker 环境下，将 localhost 替换为 redis
                                if is_docker and host == "localhost":
                                    host = "redis"
                                    logger.info(
                                        "🐳 检测到 Docker 环境，将 Redis host 从 localhost 改为 redis"
                                    )

                            if env_port:
                                port = int(env_port)

                            logger.info(
                                f"🔑 使用环境变量中的 Redis 配置 (host={host}, port={port})"
                            )

                    # 如果配置中没有数据库编号，尝试从环境变量获取
                    if database is None:
                        env_db = settings.REDIS_DB
                        if env_db is not None:
                            database = int(env_db)
                            logger.info(
                                f"📦 使用环境变量中的 Redis 数据库编号: {database}"
                            )

                    # 构建连接参数
                    redis_params = {
                        "host": host,
                        "port": port,
                        "decode_responses": True,
                        "socket_connect_timeout": 5,
                    }

                    if password:
                        redis_params["password"] = password

                    if database is not None:
                        redis_params["db"] = int(database)

                    # 创建连接并测试
                    redis_client = await aioredis.from_url(
                        f"redis://{host}:{port}", **redis_params
                    )

                    # 执行 PING 命令
                    await redis_client.ping()

                    # 获取服务器信息
                    info = await redis_client.info("server")

                    response_time = time.time() - start_time

                    # 关闭连接
                    await redis_client.aclose(close_connection_pool=True)

                    return {
                        "success": True,
                        "message": "成功连接到 Redis 数据库",
                        "response_time": response_time,
                        "details": {
                            "type": db_type,
                            "host": host,
                            "port": port,
                            "database": database,
                            "redis_version": info.get("redis_version", "unknown"),
                            "used_env_config": used_env_config,
                        },
                    }
                except ImportError:
                    return {
                        "success": False,
                        "message": "Redis 库未安装，请运行: pip install redis",
                        "response_time": time.time() - start_time,
                        "details": None,
                    }
                except Exception as e:
                    error_msg = str(e)
                    if "WRONGPASS" in error_msg or "Authentication" in error_msg:
                        message = "认证失败，请检查密码"
                    elif "Connection refused" in error_msg:
                        message = "连接被拒绝，请检查主机地址和端口"
                    elif "timed out" in error_msg.lower():
                        message = "连接超时，请检查网络和防火墙设置"
                    else:
                        message = f"连接失败: {error_msg}"

                    return {
                        "success": False,
                        "message": message,
                        "response_time": time.time() - start_time,
                        "details": None,
                    }

            elif db_type == "mysql":
                try:
                    aiomysql = importlib.import_module("aiomysql")

                    # 创建连接
                    conn = await aiomysql.connect(
                        host=db_config.host,
                        port=db_config.port,
                        user=db_config.username,
                        password=db_config.password,
                        db=db_config.database,
                        connect_timeout=5,
                    )

                    # 执行测试查询
                    async with conn.cursor() as cursor:
                        await cursor.execute("SELECT VERSION()")
                        version = await cursor.fetchone()

                    response_time = time.time() - start_time

                    # 关闭连接
                    conn.close()

                    return {
                        "success": True,
                        "message": "成功连接到 MySQL 数据库",
                        "response_time": response_time,
                        "details": {
                            "type": db_type,
                            "host": db_config.host,
                            "port": db_config.port,
                            "database": db_config.database,
                            "version": version[0] if version else "unknown",
                        },
                    }
                except ImportError:
                    return {
                        "success": False,
                        "message": "aiomysql 库未安装，请运行: pip install aiomysql",
                        "response_time": time.time() - start_time,
                        "details": None,
                    }
                except Exception as e:
                    error_msg = str(e)
                    if "Access denied" in error_msg:
                        message = "访问被拒绝，请检查用户名和密码"
                    elif "Unknown database" in error_msg:
                        message = f"数据库 '{db_config.database}' 不存在"
                    elif "Can't connect" in error_msg:
                        message = "无法连接，请检查主机地址和端口"
                    else:
                        message = f"连接失败: {error_msg}"

                    return {
                        "success": False,
                        "message": message,
                        "response_time": time.time() - start_time,
                        "details": None,
                    }

            elif db_type == "postgresql":
                try:
                    asyncpg = importlib.import_module("asyncpg")

                    # 创建连接
                    conn = await asyncpg.connect(
                        host=db_config.host,
                        port=db_config.port,
                        user=db_config.username,
                        password=db_config.password,
                        database=db_config.database,
                        timeout=5,
                    )

                    # 执行测试查询
                    version = await conn.fetchval("SELECT version()")

                    response_time = time.time() - start_time

                    # 关闭连接
                    await conn.close()

                    return {
                        "success": True,
                        "message": "成功连接到 PostgreSQL 数据库",
                        "response_time": response_time,
                        "details": {
                            "type": db_type,
                            "host": db_config.host,
                            "port": db_config.port,
                            "database": db_config.database,
                            "version": version.split()[1] if version else "unknown",
                        },
                    }
                except ImportError:
                    return {
                        "success": False,
                        "message": "asyncpg 库未安装，请运行: pip install asyncpg",
                        "response_time": time.time() - start_time,
                        "details": None,
                    }
                except Exception as e:
                    error_msg = str(e)
                    if "password authentication failed" in error_msg:
                        message = "密码认证失败，请检查用户名和密码"
                    elif "does not exist" in error_msg:
                        message = f"数据库 '{db_config.database}' 不存在"
                    elif "Connection refused" in error_msg:
                        message = "连接被拒绝，请检查主机地址和端口"
                    else:
                        message = f"连接失败: {error_msg}"

                    return {
                        "success": False,
                        "message": message,
                        "response_time": time.time() - start_time,
                        "details": None,
                    }

            elif db_type == "sqlite":
                try:
                    aiosqlite = importlib.import_module("aiosqlite")

                    # SQLite 使用文件路径，不需要 host/port
                    db_path = db_config.database or db_config.host

                    # 创建连接
                    async with aiosqlite.connect(db_path, timeout=5) as conn:
                        # 执行测试查询
                        async with conn.execute("SELECT sqlite_version()") as cursor:
                            version = await cursor.fetchone()

                    response_time = time.time() - start_time

                    return {
                        "success": True,
                        "message": "成功连接到 SQLite 数据库",
                        "response_time": response_time,
                        "details": {
                            "type": db_type,
                            "database": db_path,
                            "version": version[0] if version else "unknown",
                        },
                    }
                except ImportError:
                    return {
                        "success": False,
                        "message": "aiosqlite 库未安装，请运行: pip install aiosqlite",
                        "response_time": time.time() - start_time,
                        "details": None,
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"连接失败: {str(e)}",
                        "response_time": time.time() - start_time,
                        "details": None,
                    }

            else:
                return {
                    "success": False,
                    "message": f"不支持的数据库类型: {db_type}",
                    "response_time": time.time() - start_time,
                    "details": None,
                }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"❌ 测试数据库配置失败: {e}")
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
                "response_time": response_time,
                "details": None,
            }
