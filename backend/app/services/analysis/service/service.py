from .base import AnalysisBaseMixin
from .execute import AnalysisExecuteMixin
from .status import AnalysisStatusMixin
from .task import AnalysisTaskMixin
from .usage import AnalysisUsageMixin


class AnalysisService(
    AnalysisBaseMixin,
    AnalysisExecuteMixin,
    AnalysisTaskMixin,
    AnalysisStatusMixin,
    AnalysisUsageMixin,
):
    """股票分析服务类"""
