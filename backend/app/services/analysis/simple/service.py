from .base import BaseAnalysisMixin
from .common import logger
from .reports import AnalysisReportMixin
from .runner import AnalysisRunnerMixin
from .status import AnalysisStatusMixin
from .task import AnalysisTaskMixin


class SimpleAnalysisService(
    BaseAnalysisMixin,
    AnalysisTaskMixin,
    AnalysisRunnerMixin,
    AnalysisStatusMixin,
    AnalysisReportMixin,
):
    """简化的股票分析服务类"""


_analysis_service = None


def get_simple_analysis_service() -> SimpleAnalysisService:
    """获取分析服务实例"""
    global _analysis_service
    if _analysis_service is None:
        logger.info("🔧 [单例] 创建新的 SimpleAnalysisService 实例")
        _analysis_service = SimpleAnalysisService()
    else:
        logger.info(
            f"🔧 [单例] 返回现有的 SimpleAnalysisService 实例: {id(_analysis_service)}"
        )
    return _analysis_service
