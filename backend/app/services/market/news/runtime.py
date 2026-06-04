from .common import logger
from .service import NewsDataService

# 全局服务实例
_service_instance = None


async def get_news_data_service() -> NewsDataService:
    """获取新闻数据服务实例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = NewsDataService()
        logger.info("✅ 新闻数据服务初始化成功")
    return _service_instance
