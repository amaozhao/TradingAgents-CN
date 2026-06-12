from .common import (
    Any,
    Dict,
    Path,
    datetime,
    json,
    logger,
    timedelta,
)


class StockDataCacheMaintenanceMixin:
    def clear_old_cache(self, max_age_days: int = 7):
        """清理过期缓存"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        cleared_count = 0

        for metadata_file in self.metadata_dir.glob("*_meta.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                cached_at = datetime.fromisoformat(metadata["cached_at"])
                if cached_at < cutoff_time:
                    # 删除数据文件
                    data_file = Path(metadata["file_path"])
                    if data_file.exists():
                        data_file.unlink()

                    # 删除元数据文件
                    metadata_file.unlink()
                    cleared_count += 1

            except Exception as e:
                logger.warning(f"⚠️ 清理缓存时出错: {e}")

        logger.info(f"🧹 已清理 {cleared_count} 个过期缓存文件")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats: Dict[str, Any] = {
            "total_files": 0,
            "stock_data_count": 0,
            "news_count": 0,
            "fundamentals_count": 0,
            "total_size": 0,  # 字节
            "total_size_mb": 0,  # MB（保留用于兼容性）
            "skipped_count": 0,  # 新增：跳过的缓存数量
        }

        total_size_bytes = 0

        # 统计有元数据的缓存文件
        metadata_files_count = 0
        for metadata_file in self.metadata_dir.glob("*_meta.json"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                data_type = metadata.get("data_type", "unknown")
                if data_type == "stock_data":
                    stats["stock_data_count"] += 1
                elif data_type == "news":
                    stats["news_count"] += 1
                elif data_type == "fundamentals":
                    stats["fundamentals_count"] += 1

                # 检查是否为跳过的缓存（没有实际文件）
                data_file = Path(metadata.get("file_path", ""))
                if not data_file.exists():
                    stats["skipped_count"] += 1
                else:
                    # 计算文件大小（字节）
                    file_size = data_file.stat().st_size
                    total_size_bytes += file_size

                stats["total_files"] += 1
                metadata_files_count += 1

            except Exception:
                continue

        # 如果没有元数据文件，则直接统计缓存目录中的文件（兼容旧缓存）
        if metadata_files_count == 0:
            logger.info("📊 未找到元数据文件，直接统计缓存目录中的文件")

            # 统计各个目录中的文件
            for stock_dir, data_type in [
                (self.us_stock_dir, "us_stock"),
                (self.china_stock_dir, "china_stock"),
                (self.us_news_dir, "us_news"),
                (self.china_news_dir, "china_news"),
                (self.us_fundamentals_dir, "us_fundamentals"),
                (self.china_fundamentals_dir, "china_fundamentals"),
            ]:
                if stock_dir.exists():
                    for file_path in stock_dir.glob("*"):
                        if file_path.is_file():
                            try:
                                file_size = file_path.stat().st_size
                                total_size_bytes += file_size
                                stats["total_files"] += 1

                                # 按类型分类
                                if "stock" in data_type:
                                    stats["stock_data_count"] += 1
                                elif "news" in data_type:
                                    stats["news_count"] += 1
                                elif "fundamentals" in data_type:
                                    stats["fundamentals_count"] += 1
                            except Exception:
                                continue

        stats["total_size"] = total_size_bytes  # 字节
        stats["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)  # MB
        return stats

    def get_content_length_config_status(self) -> Dict[str, Any]:
        """获取内容长度配置状态"""
        available_providers = self._check_provider_availability()
        long_text_providers = self.content_length_config["long_text_providers"]
        available_long_providers = [
            p for p in available_providers if p in long_text_providers
        ]

        return {
            "enabled": self.content_length_config["enable_length_check"],
            "max_content_length": self.content_length_config["max_content_length"],
            "max_content_length_formatted": f"{self.content_length_config['max_content_length']:,}字符",
            "long_text_providers": long_text_providers,
            "available_providers": available_providers,
            "available_long_providers": available_long_providers,
            "has_long_text_support": len(available_long_providers) > 0,
            "will_skip_long_content": self.content_length_config["enable_length_check"]
            and len(available_long_providers) == 0,
        }
