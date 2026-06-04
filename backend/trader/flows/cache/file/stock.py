# ruff: noqa: F403,F405
from .common import *


class StockDataCacheStockMixin:
    def save_stock_data(
        self,
        symbol: str,
        data: Union[pd.DataFrame, str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = "unknown",
    ) -> str:
        """
        保存股票数据到缓存 - 支持美股和A股分类存储

        Args:
            symbol: 股票代码
            data: 股票数据（DataFrame或字符串）
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源（如 "tdx", "yfinance", "finnhub"）

        Returns:
            cache_key: 缓存键
        """
        # 检查内容长度是否需要跳过缓存
        content_to_check = str(data)
        if self.should_skip_cache_for_content(content_to_check, "股票数据"):
            # 生成一个虚拟的缓存键，但不实际保存
            market_type = self._determine_market_type(symbol)
            cache_key = self._generate_cache_key(
                "stock_data",
                symbol,
                start_date=start_date,
                end_date=end_date,
                source=data_source,
                market=market_type,
                skipped=True,
            )
            logger.info(f"🚫 股票数据因内容过长被跳过缓存: {symbol} -> {cache_key}")
            return cache_key

        market_type = self._determine_market_type(symbol)
        cache_key = self._generate_cache_key(
            "stock_data",
            symbol,
            start_date=start_date,
            end_date=end_date,
            source=data_source,
            market=market_type,
        )

        # 保存数据
        if isinstance(data, pd.DataFrame):
            cache_path = self._get_cache_path("stock_data", cache_key, "csv", symbol)
            cache_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            data.to_csv(cache_path, index=True)
        else:
            cache_path = self._get_cache_path("stock_data", cache_key, "txt", symbol)
            cache_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(str(data))

        # 保存元数据
        metadata = {
            "symbol": symbol,
            "data_type": "stock_data",
            "market_type": market_type,
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "file_path": str(cache_path),
            "file_format": "csv" if isinstance(data, pd.DataFrame) else "txt",
            "content_length": len(content_to_check),
        }
        self._save_metadata(cache_key, metadata)

        # 获取描述信息
        cache_type = f"{market_type}_stock_data"
        desc = self.cache_config.get(cache_type, {}).get("description", "股票数据")
        logger.info(f"💾 {desc}已缓存: {symbol} ({data_source}) -> {cache_key}")
        return cache_key

    def load_stock_data(self, cache_key: str) -> Optional[Union[pd.DataFrame, str]]:
        """从缓存加载股票数据"""
        metadata = self._load_metadata(cache_key)
        if not metadata:
            return None

        cache_path = Path(metadata["file_path"])
        if not cache_path.exists():
            return None

        try:
            if metadata["file_format"] == "csv":
                return pd.read_csv(cache_path, index_col=0)
            else:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"⚠️ 加载缓存数据失败: {e}")
            return None

    def find_cached_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: Optional[str] = None,
        max_age_hours: Optional[int] = None,
    ) -> Optional[str]:
        """
        查找匹配的缓存数据 - 支持智能市场分类查找

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源
            max_age_hours: 最大缓存时间（小时），None时使用智能配置

        Returns:
            cache_key: 如果找到有效缓存则返回缓存键，否则返回None
        """
        market_type = self._determine_market_type(symbol)

        # 如果没有指定TTL，使用智能配置
        if max_age_hours is None:
            cache_type = f"{market_type}_stock_data"
            max_age_hours = self.cache_config.get(cache_type, {}).get("ttl_hours", 24)

        # 生成查找键
        search_key = self._generate_cache_key(
            "stock_data",
            symbol,
            start_date=start_date,
            end_date=end_date,
            source=data_source,
            market=market_type,
        )

        # 检查精确匹配
        if self.is_cache_valid(search_key, max_age_hours, symbol, "stock_data"):
            desc = self.cache_config.get(f"{market_type}_stock_data", {}).get(
                "description", "数据"
            )
            logger.info(f"🎯 找到精确匹配的{desc}: {symbol} -> {search_key}")
            return search_key

        # 如果没有精确匹配，查找部分匹配（相同股票代码的其他缓存）
        for metadata_file in self.metadata_dir.glob("*_meta.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                if (
                    metadata.get("symbol") == symbol
                    and metadata.get("data_type") == "stock_data"
                    and metadata.get("market_type") == market_type
                    and (
                        data_source is None
                        or metadata.get("data_source") == data_source
                    )
                ):
                    cache_key = metadata_file.stem.replace("_meta", "")
                    if self.is_cache_valid(
                        cache_key, max_age_hours, symbol, "stock_data"
                    ):
                        desc = self.cache_config.get(
                            f"{market_type}_stock_data", {}
                        ).get("description", "数据")
                        logger.info(f"📋 找到部分匹配的{desc}: {symbol} -> {cache_key}")
                        return cache_key
            except Exception:
                continue

        desc = self.cache_config.get(f"{market_type}_stock_data", {}).get(
            "description", "数据"
        )
        logger.error(f"❌ 未找到有效的{desc}缓存: {symbol}")
        return None
