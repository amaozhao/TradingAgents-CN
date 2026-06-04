# ruff: noqa: F403,F405
from .common import *


class StockDataCachePolicyMixin:
    def should_skip_cache_for_content(
        self, content: str, data_type: str = "unknown"
    ) -> bool:
        """
        判断是否因为内容超长而跳过缓存

        Args:
            content: 要缓存的内容
            data_type: 数据类型（用于日志）

        Returns:
            bool: 是否应该跳过缓存
        """
        # 如果未启用长度检查，直接返回False
        if not self.content_length_config["enable_length_check"]:
            return False

        # 检查内容长度
        content_length = len(content)
        max_length = self.content_length_config["max_content_length"]

        if content_length <= max_length:
            return False

        # 内容超长，检查是否有可用的长文本处理提供商
        available_providers = self._check_provider_availability()
        long_text_providers = self.content_length_config["long_text_providers"]

        # 找到可用的长文本提供商
        available_long_providers = [
            p for p in available_providers if p in long_text_providers
        ]

        if not available_long_providers:
            logger.warning(
                f"⚠️ 内容过长({content_length:,}字符 > {max_length:,}字符)且无可用长文本提供商，跳过{data_type}缓存"
            )
            logger.info(f"💡 可用提供商: {available_providers}")
            logger.info(f"💡 长文本提供商: {long_text_providers}")
            return True
        else:
            logger.info(
                f"✅ 内容较长({content_length:,}字符)但有可用长文本提供商({available_long_providers})，继续缓存"
            )
            return False

    def _generate_cache_key(self, data_type: str, symbol: str, **kwargs) -> str:
        """生成缓存键"""
        # 创建一个包含所有参数的字符串
        params_str = f"{data_type}_{symbol}"
        for key, value in sorted(kwargs.items()):
            params_str += f"_{key}_{value}"

        # 使用MD5生成短的唯一标识
        cache_key = hashlib.md5(params_str.encode()).hexdigest()[:12]
        return f"{symbol}_{data_type}_{cache_key}"

    def _get_cache_path(
        self,
        data_type: str,
        cache_key: str,
        file_format: str = "json",
        symbol: Optional[str] = None,
    ) -> Path:
        """获取缓存文件路径 - 支持市场分类"""
        if symbol:
            market_type = self._determine_market_type(symbol)
        else:
            # 从缓存键中尝试提取市场类型
            market_type = (
                "us"
                if not cache_key.startswith(
                    ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")
                )
                else "china"
            )

        # 根据数据类型和市场类型选择目录
        if data_type == "stock_data":
            base_dir = (
                self.china_stock_dir if market_type == "china" else self.us_stock_dir
            )
        elif data_type == "news":
            base_dir = (
                self.china_news_dir if market_type == "china" else self.us_news_dir
            )
        elif data_type == "fundamentals":
            base_dir = (
                self.china_fundamentals_dir
                if market_type == "china"
                else self.us_fundamentals_dir
            )
        else:
            base_dir = self.cache_dir

        return base_dir / f"{cache_key}.{file_format}"

    def _get_metadata_path(self, cache_key: str) -> Path:
        """获取元数据文件路径"""
        return self.metadata_dir / f"{cache_key}_meta.json"

    def _save_metadata(self, cache_key: str, metadata: Dict[str, Any]):
        """保存元数据"""
        metadata_path = self._get_metadata_path(cache_key)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        metadata["cached_at"] = datetime.now().isoformat()

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _load_metadata(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """加载元数据"""
        metadata_path = self._get_metadata_path(cache_key)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"⚠️ 加载元数据失败: {e}")
            return None

    def is_cache_valid(
        self,
        cache_key: str,
        max_age_hours: Optional[int] = None,
        symbol: Optional[str] = None,
        data_type: Optional[str] = None,
    ) -> bool:
        """检查缓存是否有效 - 支持智能TTL配置"""
        metadata = self._load_metadata(cache_key)
        if not metadata:
            return False

        # 如果没有指定TTL，根据数据类型和市场自动确定
        if max_age_hours is None:
            if symbol and data_type:
                market_type = self._determine_market_type(symbol)
                cache_type = f"{market_type}_{data_type}"
                max_age_hours = self.cache_config.get(cache_type, {}).get(
                    "ttl_hours", 24
                )
            else:
                # 从元数据中获取信息
                symbol = str(metadata.get("symbol") or "")
                data_type = metadata.get("data_type", "stock_data")
                market_type = self._determine_market_type(symbol)
                cache_type = f"{market_type}_{data_type}"
                max_age_hours = self.cache_config.get(cache_type, {}).get(
                    "ttl_hours", 24
                )
        if max_age_hours is None:
            max_age_hours = 24

        cached_at = datetime.fromisoformat(metadata["cached_at"])
        age = datetime.now() - cached_at

        is_valid = age.total_seconds() < max_age_hours * 3600

        if is_valid:
            market_type = self._determine_market_type(metadata.get("symbol", ""))
            cache_type = f"{market_type}_{metadata.get('data_type', 'stock_data')}"
            desc = self.cache_config.get(cache_type, {}).get("description", "数据")
            logger.info(
                f"✅ 缓存有效: {desc} - {metadata.get('symbol')} (剩余 {max_age_hours - age.total_seconds() / 3600:.1f}h)"
            )

        return is_valid
