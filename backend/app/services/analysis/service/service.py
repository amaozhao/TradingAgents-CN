from .base import AnalysisBaseMixin
from .execute import AnalysisExecuteMixin
from .status import AnalysisStatusMixin
from .submit import AnalysisSubmitMixin
from .task import AnalysisTaskMixin
from .usage import AnalysisUsageMixin


class AnalysisService(
    AnalysisBaseMixin,
    AnalysisExecuteMixin,
    AnalysisSubmitMixin,
    AnalysisTaskMixin,
    AnalysisStatusMixin,
    AnalysisUsageMixin,
):
    """股票分析服务类"""
