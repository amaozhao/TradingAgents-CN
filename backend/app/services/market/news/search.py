from .common import (
    Any,
    Dict,
    List,
    Optional,
    cast,
)
from .models import convert_document_id_to_str


class NewsSearchMixin:
    async def search_news(
        self, query_text: str, symbol: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        全文搜索新闻

        Args:
            query_text: 搜索文本
            symbol: 股票代码过滤
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        try:
            collection = self._get_collection()

            # 构建查询条件
            query: Dict[str, Any] = {"$text": {"$search": query_text}}

            if symbol:
                query["symbol"] = symbol

            # 执行搜索，按相关性排序
            cursor = collection.find(query, {"score": {"$meta": "textScore"}}).sort(
                [("score", {"$meta": "textScore"})]
            )

            cursor = cursor.limit(limit)
            results = await cursor.to_list(length=None)

            # 🔧 转换 DocumentId 为字符串，避免 JSON 序列化错误
            results = cast(List[Dict[str, Any]], convert_document_id_to_str(results))

            self.logger.info(f"🔍 全文搜索返回 {len(results)} 条结果")
            return results

        except Exception as e:
            self.logger.error(f"❌ 全文搜索失败: {e}")
            return []
