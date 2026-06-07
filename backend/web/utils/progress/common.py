# ruff: noqa: F401,F403,F405,F821
def get_progress_by_id(analysis_id: str) -> Optional[Dict[str, Any]]:
    """根据分析ID获取进度"""
    try:
        # 如果Redis启用，先尝试Redis
        if settings.REDIS_ENABLED:
            try:
                redis = importlib.import_module("redis")

                # 创建Redis连接
                if settings.REDIS_PASSWORD:
                    redis_client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        password=settings.REDIS_PASSWORD,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                    )
                else:
                    redis_client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                    )

                key = f"progress:{analysis_id}"
                data = redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug(f"📊 [异步进度] Redis读取失败: {e}")

        # 尝试文件
        progress_file = f"./data/progress_{analysis_id}.json"
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as f:
                return json.load(f)

        return None
    except Exception as e:
        logger.error(f"📊 [异步进度] 获取进度失败: {analysis_id}, 错误: {e}")
        return None


def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def get_latest_analysis_id() -> Optional[str]:
    """获取最新的分析ID"""
    try:
        # 如果Redis启用，先尝试从Redis获取
        if settings.REDIS_ENABLED:
            try:
                redis = importlib.import_module("redis")

                # 创建Redis连接
                if settings.REDIS_PASSWORD:
                    redis_client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        password=settings.REDIS_PASSWORD,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                    )
                else:
                    redis_client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                    )

                # 获取所有progress键
                keys = redis_client.keys("progress:*")
                if not keys:
                    return None

                # 获取每个键的数据，找到最新的
                latest_time = 0
                latest_id = None

                for key in keys:
                    try:
                        data = redis_client.get(key)
                        if data:
                            progress_data = json.loads(data)
                            last_update = progress_data.get("last_update", 0)
                            if last_update > latest_time:
                                latest_time = last_update
                                # 从键名中提取analysis_id (去掉"progress:"前缀)
                                latest_id = key.replace("progress:", "")
                    except Exception:
                        continue

                if latest_id:
                    logger.info(f"📊 [恢复分析] 找到最新分析ID: {latest_id}")
                    return latest_id

            except Exception as e:
                logger.debug(f"📊 [恢复分析] Redis查找失败: {e}")

        # 如果Redis失败或未启用，尝试从文件查找
        data_dir = Path("data")
        if data_dir.exists():
            progress_files = list(data_dir.glob("progress_*.json"))
            if progress_files:
                # 按修改时间排序，获取最新的
                latest_file = max(progress_files, key=lambda f: f.stat().st_mtime)
                # 从文件名提取analysis_id
                filename = latest_file.name
                if filename.startswith("progress_") and filename.endswith(".json"):
                    analysis_id = filename[9:-5]  # 去掉前缀和后缀
                    logger.debug(f"📊 [恢复分析] 从文件找到最新分析ID: {analysis_id}")
                    return analysis_id

        return None
    except Exception as e:
        logger.error(f"📊 [恢复分析] 获取最新分析ID失败: {e}")
        return None
