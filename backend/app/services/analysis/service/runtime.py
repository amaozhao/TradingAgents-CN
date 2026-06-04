# ruff: noqa: F403,F405
from .common import *
from .service import AnalysisService

# 全局分析服务实例（延迟初始化）
analysis_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    """获取分析服务实例（延迟初始化）"""
    global analysis_service
    if analysis_service is None:
        analysis_service = AnalysisService()
    return analysis_service
