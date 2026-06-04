# ruff: noqa: F403,F405
from .common import *


class StockDataCacheBaseMixin:
    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径，默认为 trader/dataflows/data_cache
        """
        if cache_dir is None:
            # 获取当前文件所在目录
            current_dir = Path(__file__).parent
            cache_dir = current_dir / "data_cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # 创建子目录 - 按市场分类
        self.us_stock_dir = self.cache_dir / "us_stocks"
        self.china_stock_dir = self.cache_dir / "china_stocks"
        self.us_news_dir = self.cache_dir / "us_news"
        self.china_news_dir = self.cache_dir / "china_news"
        self.us_fundamentals_dir = self.cache_dir / "us_fundamentals"
        self.china_fundamentals_dir = self.cache_dir / "china_fundamentals"
        self.metadata_dir = self.cache_dir / "metadata"

        # 创建所有目录
        for dir_path in [
            self.us_stock_dir,
            self.china_stock_dir,
            self.us_news_dir,
            self.china_news_dir,
            self.us_fundamentals_dir,
            self.china_fundamentals_dir,
            self.metadata_dir,
        ]:
            dir_path.mkdir(exist_ok=True)

        # 缓存配置 - 针对不同市场设置不同的TTL
        self.cache_config = {
            "us_stock_data": {
                "ttl_hours": 2,  # 美股数据缓存2小时（考虑到API限制）
                "max_files": 1000,
                "description": "美股历史数据",
            },
            "china_stock_data": {
                "ttl_hours": 1,  # A股数据缓存1小时（实时性要求高）
                "max_files": 1000,
                "description": "A股历史数据",
            },
            "us_news": {
                "ttl_hours": 6,  # 美股新闻缓存6小时
                "max_files": 500,
                "description": "美股新闻数据",
            },
            "china_news": {
                "ttl_hours": 4,  # A股新闻缓存4小时
                "max_files": 500,
                "description": "A股新闻数据",
            },
            "us_fundamentals": {
                "ttl_hours": 24,  # 美股基本面数据缓存24小时
                "max_files": 200,
                "description": "美股基本面数据",
            },
            "china_fundamentals": {
                "ttl_hours": 12,  # A股基本面数据缓存12小时
                "max_files": 200,
                "description": "A股基本面数据",
            },
        }

        # 内容长度限制配置（文件缓存默认不限制）
        self.content_length_config = {
            "max_content_length": int(
                os.getenv("MAX_CACHE_CONTENT_LENGTH", "50000")
            ),  # 50K字符
            "long_text_providers": [
                "dashscope",
                "openai",
                "google",
            ],  # 支持长文本的提供商
            "enable_length_check": os.getenv(
                "ENABLE_CACHE_LENGTH_CHECK", "false"
            ).lower()
            == "true",  # 文件缓存默认不限制
        }

        logger.info(f"📁 缓存管理器初始化完成，缓存目录: {self.cache_dir}")
        logger.info("🗄️ 数据库缓存管理器初始化完成")
        logger.info("   美股数据: ✅ 已配置")
        logger.info("   A股数据: ✅ 已配置")

    def _determine_market_type(self, symbol: str) -> str:
        """根据股票代码确定市场类型"""
        re = importlib.import_module("re")

        # 判断是否为中国A股（6位数字）
        if re.match(r"^\d{6}$", str(symbol)):
            return "china"
        else:
            return "us"

    def _check_provider_availability(self) -> List[str]:
        """检查可用的LLM提供商"""
        available_providers = []

        # 检查DashScope
        dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        if dashscope_key and dashscope_key.strip():
            available_providers.append("dashscope")

        # 检查OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.strip():
            # 简单的格式检查
            if openai_key.startswith("sk-") and len(openai_key) >= 40:
                available_providers.append("openai")

        # 检查Google AI
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key and google_key.strip():
            available_providers.append("google")

        # 检查Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and anthropic_key.strip():
            available_providers.append("anthropic")

        return available_providers
