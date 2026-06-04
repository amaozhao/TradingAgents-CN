# ruff: noqa: F403,F405
from .common import *


def convert_document_id_to_str(
    data: Union[Dict, List[Dict]],
) -> Union[Dict, List[Dict]]:
    """
    转换 PostgreSQL DocumentId 为字符串，避免 JSON 序列化错误

    Args:
        data: 单个文档或文档列表

    Returns:
        转换后的数据
    """
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "_id" in item:
                item["_id"] = str(item["_id"])
        return data
    elif isinstance(data, dict):
        if "_id" in data:
            data["_id"] = str(data["_id"])
        return data
    return data


@dataclass
class NewsQueryParams:
    """新闻查询参数"""

    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    importance: Optional[str] = None
    data_source: Optional[str] = None
    keywords: Optional[List[str]] = None
    limit: int = 50
    skip: int = 0
    sort_by: str = "publish_time"
    sort_order: int = -1  # -1 for desc, 1 for asc


@dataclass
class NewsStats:
    """新闻统计信息"""

    total_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    high_importance_count: int = 0
    medium_importance_count: int = 0
    low_importance_count: int = 0
    categories: Dict[str, int] = field(default_factory=dict)
    sources: Dict[str, int] = field(default_factory=dict)
