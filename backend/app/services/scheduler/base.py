from .common import AsyncIOScheduler, get_postgres_db


class SchedulerBaseMixin:
    def __init__(self, scheduler: AsyncIOScheduler):
        """
        初始化服务

        Args:
            scheduler: APScheduler调度器实例
        """
        self.scheduler = scheduler
        self.db = None

        # 添加事件监听器，监控任务执行
        self._setup_event_listeners()

    def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            self.db = get_postgres_db()
        return self.db
