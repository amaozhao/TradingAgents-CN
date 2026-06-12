from .common import (
    Dict,
    List,
    Optional,
    json,
    logger,
)


class ForeignStockCacheMixin:
    def _parse_cached_data(
        self, cached_data: str, market: str, code: str
    ) -> Optional[Dict]:
        """解析缓存的数据"""
        try:
            # 尝试解析JSON
            if isinstance(cached_data, str):
                data = json.loads(cached_data)
            else:
                data = cached_data

            # 确保包含必要字段
            if isinstance(data, dict):
                data["market"] = market
                data["code"] = code
                return data
            else:
                raise ValueError("缓存数据格式错误")
        except Exception as e:
            logger.warning(f"⚠️ 解析缓存数据失败: {e}")
            # 返回空数据，触发重新获取
            return None

    def _parse_cached_kline(self, cached_data: str) -> List[Dict]:
        """解析缓存的K线数据"""
        try:
            # 尝试解析JSON
            if isinstance(cached_data, str):
                data = json.loads(cached_data)
            else:
                data = cached_data

            # 确保是列表
            if isinstance(data, list):
                return data
            else:
                raise ValueError("缓存K线数据格式错误")
        except Exception as e:
            logger.warning(f"⚠️ 解析缓存K线数据失败: {e}")
            # 返回空列表，触发重新获取
            return []

    def _safe_float(self, value, default=None):
        """安全地转换为浮点数，处理 'None' 字符串和空值"""
        if value is None or value == "" or value == "None" or value == "N/A":
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
