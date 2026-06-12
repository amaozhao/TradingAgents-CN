from .common import (
    Optional,
    Path,
    datetime,
    json,
    logger,
)


class StockDataCacheFundamentalsMixin:
    def save_fundamentals_data(
        self, symbol: str, fundamentals_data: str, data_source: str = "unknown"
    ) -> str:
        """保存基本面数据到缓存"""
        # 检查内容长度是否需要跳过缓存
        if self.should_skip_cache_for_content(fundamentals_data, "基本面数据"):
            # 生成一个虚拟的缓存键，但不实际保存
            market_type = self._determine_market_type(symbol)
            cache_key = self._generate_cache_key(
                "fundamentals",
                symbol,
                source=data_source,
                market=market_type,
                date=datetime.now().strftime("%Y-%m-%d"),
                skipped=True,
            )
            logger.info(f"🚫 基本面数据因内容过长被跳过缓存: {symbol} -> {cache_key}")
            return cache_key

        market_type = self._determine_market_type(symbol)
        cache_key = self._generate_cache_key(
            "fundamentals",
            symbol,
            source=data_source,
            market=market_type,
            date=datetime.now().strftime("%Y-%m-%d"),
        )

        cache_path = self._get_cache_path("fundamentals", cache_key, "txt", symbol)
        cache_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(fundamentals_data)

        metadata = {
            "symbol": symbol,
            "data_type": "fundamentals",
            "data_source": data_source,
            "market_type": market_type,
            "file_path": str(cache_path),
            "file_format": "txt",
            "content_length": len(fundamentals_data),
        }
        self._save_metadata(cache_key, metadata)

        desc = self.cache_config.get(f"{market_type}_fundamentals", {}).get(
            "description", "基本面数据"
        )
        logger.info(f"💼 {desc}已缓存: {symbol} ({data_source}) -> {cache_key}")
        return cache_key

    def load_fundamentals_data(self, cache_key: str) -> Optional[str]:
        """从缓存加载基本面数据"""
        metadata = self._load_metadata(cache_key)
        if not metadata:
            return None

        cache_path = Path(metadata["file_path"])
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"⚠️ 加载基本面缓存数据失败: {e}")
            return None

    def find_cached_fundamentals_data(
        self,
        symbol: str,
        data_source: Optional[str] = None,
        max_age_hours: Optional[int] = None,
    ) -> Optional[str]:
        """
        查找匹配的基本面缓存数据

        Args:
            symbol: 股票代码
            data_source: 数据源（如 "openai", "finnhub"）
            max_age_hours: 最大缓存时间（小时），None时使用智能配置

        Returns:
            cache_key: 如果找到有效缓存则返回缓存键，否则返回None
        """
        market_type = self._determine_market_type(symbol)

        # 如果没有指定TTL，使用智能配置
        if max_age_hours is None:
            cache_type = f"{market_type}_fundamentals"
            max_age_hours = self.cache_config.get(cache_type, {}).get("ttl_hours", 24)

        # 查找匹配的缓存
        for metadata_file in self.metadata_dir.glob("*_meta.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                if (
                    metadata.get("symbol") == symbol
                    and metadata.get("data_type") == "fundamentals"
                    and metadata.get("market_type") == market_type
                    and (
                        data_source is None
                        or metadata.get("data_source") == data_source
                    )
                ):
                    cache_key = metadata_file.stem.replace("_meta", "")
                    if self.is_cache_valid(
                        cache_key, max_age_hours, symbol, "fundamentals"
                    ):
                        desc = self.cache_config.get(
                            f"{market_type}_fundamentals", {}
                        ).get("description", "基本面数据")
                        logger.info(
                            f"🎯 找到匹配的{desc}缓存: {symbol} ({data_source}) -> {cache_key}"
                        )
                        return cache_key
            except Exception:
                continue

        desc = self.cache_config.get(f"{market_type}_fundamentals", {}).get(
            "description", "基本面数据"
        )
        logger.error(f"❌ 未找到有效的{desc}缓存: {symbol} ({data_source})")
        return None
