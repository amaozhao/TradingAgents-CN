# ruff: noqa: F401,F403,F405,F821
class TushareSyncService(
    _TushareSyncServiceMixin1, _TushareSyncServiceMixin2, _TushareSyncServiceMixin3
):
    """
    Tushare数据同步服务
    负责将Tushare数据同步到PostgreSQL标准化集合
    """
