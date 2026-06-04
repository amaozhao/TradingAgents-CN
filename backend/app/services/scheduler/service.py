from .base import SchedulerBaseMixin
from .events import SchedulerEventsMixin
from .history import SchedulerHistoryMixin
from .jobs import SchedulerJobsMixin
from .metadata import SchedulerMetadataMixin
from .stats import SchedulerStatsMixin


class SchedulerService(
    SchedulerBaseMixin,
    SchedulerJobsMixin,
    SchedulerHistoryMixin,
    SchedulerStatsMixin,
    SchedulerEventsMixin,
    SchedulerMetadataMixin,
):
    """定时任务管理服务"""
