# ruff: noqa: F403,F405
from .common import *


class ForeignStockPublicMixin:
    async def get_quote(
        self, market: str, code: str, force_refresh: bool = False
    ) -> Dict:
        """
        获取实时行情

        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            force_refresh: 是否强制刷新（跳过缓存）

        Returns:
            实时行情数据

        流程：
        1. 检查是否强制刷新
        2. 从缓存获取（Redis → PostgreSQL → File）
        3. 缓存未命中 → 调用数据源API（按优先级）
        4. 保存到缓存
        """
        if market == "HK":
            return await self._get_hk_quote(code, force_refresh)
        elif market == "US":
            return await self._get_us_quote(code, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")

    async def get_basic_info(
        self, market: str, code: str, force_refresh: bool = False
    ) -> Dict:
        """
        获取基础信息

        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            force_refresh: 是否强制刷新

        Returns:
            基础信息数据
        """
        if market == "HK":
            return await self._get_hk_info(code, force_refresh)
        elif market == "US":
            return await self._get_us_info(code, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")

    async def get_kline(
        self,
        market: str,
        code: str,
        period: str = "day",
        limit: int = 120,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        获取K线数据

        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            period: 周期 (day/week/month)
            limit: 数据条数
            force_refresh: 是否强制刷新

        Returns:
            K线数据列表
        """
        if market == "HK":
            return await self._get_hk_kline(code, period, limit, force_refresh)
        elif market == "US":
            return await self._get_us_kline(code, period, limit, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
