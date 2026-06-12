from .common import Optional, logger


class StockDataCacheNewsMixin:
    def save_news_data(
        self,
        symbol: str,
        news_data: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = "unknown",
    ) -> str:
        """保存新闻数据到缓存"""
        # 检查内容长度是否需要跳过缓存
        if self.should_skip_cache_for_content(news_data, "新闻数据"):
            # 生成一个虚拟的缓存键，但不实际保存
            cache_key = self._generate_cache_key(
                "news",
                symbol,
                start_date=start_date,
                end_date=end_date,
                source=data_source,
                skipped=True,
            )
            logger.info(f"🚫 新闻数据因内容过长被跳过缓存: {symbol} -> {cache_key}")
            return cache_key

        cache_key = self._generate_cache_key(
            "news", symbol, start_date=start_date, end_date=end_date, source=data_source
        )

        cache_path = self._get_cache_path("news", cache_key, "txt")
        cache_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(news_data)

        metadata = {
            "symbol": symbol,
            "data_type": "news",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "file_path": str(cache_path),
            "file_format": "txt",
            "content_length": len(news_data),
        }
        self._save_metadata(cache_key, metadata)

        logger.info(f"📰 新闻数据已缓存: {symbol} ({data_source}) -> {cache_key}")
        return cache_key
