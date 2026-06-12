from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imports import (
        Any,
        Dict,
        Path,
        get_cache_dir,
        get_int,
        importlib,
        json,
        logger,
        os,
        pd,
        time,
    )

class ImprovedHKStockProvider:
    """改进的港股数据提供器"""

    def __init__(self):
        # 将缓存文件写入到统一的数据缓存目录下，避免污染项目根目录
        hk_cache_dir = get_cache_dir("hk")
        if isinstance(hk_cache_dir, Path):
            self.cache_file = str(hk_cache_dir.joinpath("hk_stock_cache.json"))
        else:
            self.cache_file = os.path.join(hk_cache_dir, "hk_stock_cache.json")

        self.cache_ttl = get_int("TA_HK_CACHE_TTL_SECONDS", "ta_hk_cache_ttl_seconds", 3600 * 24)
        self.rate_limit_wait = get_int("TA_HK_RATE_LIMIT_WAIT_SECONDS", "ta_hk_rate_limit_wait_seconds", 5)
        self.last_request_time = 0

        # 内置港股名称映射（避免API调用）
        self.hk_stock_names = {
            # 腾讯系
            "0700.HK": "腾讯控股",
            "0700": "腾讯控股",
            "00700": "腾讯控股",
            # 电信运营商
            "0941.HK": "中国移动",
            "0941": "中国移动",
            "00941": "中国移动",
            "0762.HK": "中国联通",
            "0762": "中国联通",
            "00762": "中国联通",
            "0728.HK": "中国电信",
            "0728": "中国电信",
            "00728": "中国电信",
            # 银行
            "0939.HK": "建设银行",
            "0939": "建设银行",
            "00939": "建设银行",
            "1398.HK": "工商银行",
            "1398": "工商银行",
            "01398": "工商银行",
            "3988.HK": "中国银行",
            "3988": "中国银行",
            "03988": "中国银行",
            "0005.HK": "汇丰控股",
            "0005": "汇丰控股",
            "00005": "汇丰控股",
            # 保险
            "1299.HK": "友邦保险",
            "1299": "友邦保险",
            "01299": "友邦保险",
            "2318.HK": "中国平安",
            "2318": "中国平安",
            "02318": "中国平安",
            "2628.HK": "中国人寿",
            "2628": "中国人寿",
            "02628": "中国人寿",
            # 石油化工
            "0857.HK": "中国石油",
            "0857": "中国石油",
            "00857": "中国石油",
            "0386.HK": "中国石化",
            "0386": "中国石化",
            "00386": "中国石化",
            # 地产
            "1109.HK": "华润置地",
            "1109": "华润置地",
            "01109": "华润置地",
            "1997.HK": "九龙仓置业",
            "1997": "九龙仓置业",
            "01997": "九龙仓置业",
            # 科技
            "9988.HK": "阿里巴巴",
            "9988": "阿里巴巴",
            "09988": "阿里巴巴",
            "3690.HK": "美团",
            "3690": "美团",
            "03690": "美团",
            "1024.HK": "快手",
            "1024": "快手",
            "01024": "快手",
            "9618.HK": "京东集团",
            "9618": "京东集团",
            "09618": "京东集团",
            # 消费
            "1876.HK": "百威亚太",
            "1876": "百威亚太",
            "01876": "百威亚太",
            "0291.HK": "华润啤酒",
            "0291": "华润啤酒",
            "00291": "华润啤酒",
            # 医药
            "1093.HK": "石药集团",
            "1093": "石药集团",
            "01093": "石药集团",
            "0867.HK": "康师傅",
            "0867": "康师傅",
            "00867": "康师傅",
            # 汽车
            "2238.HK": "广汽集团",
            "2238": "广汽集团",
            "02238": "广汽集团",
            "1211.HK": "比亚迪",
            "1211": "比亚迪",
            "01211": "比亚迪",
            # 航空
            "0753.HK": "中国国航",
            "0753": "中国国航",
            "00753": "中国国航",
            "0670.HK": "中国东航",
            "0670": "中国东航",
            "00670": "中国东航",
            # 钢铁
            "0347.HK": "鞍钢股份",
            "0347": "鞍钢股份",
            "00347": "鞍钢股份",
            # 电力
            "0902.HK": "华能国际",
            "0902": "华能国际",
            "00902": "华能国际",
            "0991.HK": "大唐发电",
            "0991": "大唐发电",
            "00991": "大唐发电",
        }

        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            else:
                self.cache = {}
        except Exception as e:
            logger.debug(f"📊 [港股缓存] 加载缓存失败: {e}")
            self.cache = {}

    def _save_cache(self):
        """保存缓存"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"📊 [港股缓存] 保存缓存失败: {e}")

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache:
            return False

        cache_time = self.cache[key].get("timestamp", 0)
        return (time.time() - cache_time) < self.cache_ttl

    def _rate_limit(self):
        """速率限制：确保两次请求之间有足够的间隔"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_wait:
            wait_time = self.rate_limit_wait - time_since_last_request
            logger.debug(f"⏱️ [速率限制] 等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def _normalize_hk_symbol(self, symbol: str) -> str:
        """标准化港股代码"""
        # 移除.HK后缀
        clean_symbol = symbol.replace(".HK", "").replace(".hk", "")

        # 补齐到5位数字
        if len(clean_symbol) == 4:
            clean_symbol = "0" + clean_symbol
        elif len(clean_symbol) == 3:
            clean_symbol = "00" + clean_symbol
        elif len(clean_symbol) == 2:
            clean_symbol = "000" + clean_symbol
        elif len(clean_symbol) == 1:
            clean_symbol = "0000" + clean_symbol

        return clean_symbol

    def get_company_name(self, symbol: str) -> str:
        """
        获取港股公司名称

        Args:
            symbol: 港股代码

        Returns:
            str: 公司名称
        """
        try:
            # 检查缓存
            cache_key = f"name_{symbol}"
            if self._is_cache_valid(cache_key):
                cached_name = self.cache[cache_key]["data"]
                logger.debug(f"📊 [港股缓存] 从缓存获取公司名称: {symbol} -> {cached_name}")
                return cached_name

            # 方案1：使用内置映射
            normalized_symbol = self._normalize_hk_symbol(symbol)

            # 尝试多种格式匹配
            for format_symbol in [symbol, normalized_symbol, f"{normalized_symbol}.HK"]:
                if format_symbol in self.hk_stock_names:
                    company_name = self.hk_stock_names[format_symbol]

                    # 缓存结果
                    self.cache[cache_key] = {
                        "data": company_name,
                        "timestamp": time.time(),
                        "source": "builtin_mapping",
                    }
                    self._save_cache()

                    logger.debug(f"📊 [港股映射] 获取公司名称: {symbol} -> {company_name}")
                    return company_name

            # 方案2：优先尝试AKShare API获取（有速率限制保护）
            try:
                # 速率限制保护
                current_time = time.time()
                if current_time - self.last_request_time < self.rate_limit_wait:
                    wait_time = self.rate_limit_wait - (current_time - self.last_request_time)
                    logger.debug(f"📊 [港股API] 速率限制保护，等待 {wait_time:.1f} 秒")
                    time.sleep(wait_time)

                self.last_request_time = time.time()

                # 优先尝试AKShare获取
                try:
                    # 直接使用 akshare 库获取，避免循环调用
                    logger.debug(f"📊 [港股API] 优先使用AKShare获取: {symbol}")

                    ak = importlib.import_module("akshare")
                    # 标准化代码格式（akshare 需要 5 位数字格式）
                    normalized_symbol = self._normalize_hk_symbol(symbol)

                    # 尝试获取港股实时行情（包含名称）
                    try:
                        # 使用新浪财经接口（更稳定）
                        df = ak.stock_hk_spot()
                        if df is not None and not df.empty:
                            # 查找匹配的股票
                            matched = df[df["代码"] == normalized_symbol]
                            if not matched.empty:
                                # 新浪接口返回的列名是 '中文名称'
                                akshare_name = matched.iloc[0]["中文名称"]
                                if akshare_name and not str(akshare_name).startswith("港股"):
                                    # 缓存AKShare结果
                                    self.cache[cache_key] = {
                                        "data": akshare_name,
                                        "timestamp": time.time(),
                                        "source": "akshare_sina",
                                    }
                                    self._save_cache()

                                    logger.debug(f"📊 [港股AKShare-新浪] 获取公司名称: {symbol} -> {akshare_name}")
                                    return akshare_name
                    except Exception as e:
                        logger.debug(f"📊 [港股AKShare-新浪] 获取实时行情失败: {e}")

                except Exception as e:
                    logger.debug(f"📊 [港股AKShare] AKShare获取失败: {e}")

                # 备用：尝试从统一接口获取（包含Yahoo Finance）
                get_hk_stock_info_unified = getattr(
                    importlib.import_module("trader.flows.interface"),
                    "get_hk_stock_info_unified",
                )
                hk_info = get_hk_stock_info_unified(symbol)

                if hk_info and isinstance(hk_info, dict) and "name" in hk_info:
                    api_name = hk_info["name"]
                    if not api_name.startswith("港股"):
                        # 缓存API结果
                        self.cache[cache_key] = {
                            "data": api_name,
                            "timestamp": time.time(),
                            "source": "unified_api",
                        }
                        self._save_cache()

                        logger.debug(f"📊 [港股统一API] 获取公司名称: {symbol} -> {api_name}")
                        return api_name

            except Exception as e:
                logger.debug(f"📊 [港股API] API获取失败: {e}")

            # 方案3：生成友好的默认名称
            clean_symbol = self._normalize_hk_symbol(symbol)
            default_name = f"港股{clean_symbol}"

            # 缓存默认结果（较短的TTL）
            self.cache[cache_key] = {
                "data": default_name,
                "timestamp": time.time() - self.cache_ttl + 3600,  # 1小时后过期
                "source": "default",
            }
            self._save_cache()

            logger.debug(f"📊 [港股默认] 使用默认名称: {symbol} -> {default_name}")
            return default_name

        except Exception as e:
            logger.error(f"❌ [港股] 获取公司名称失败: {e}")
            clean_symbol = self._normalize_hk_symbol(symbol)
            return f"港股{clean_symbol}"

    def get_financial_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股财务指标

        使用 AKShare 的 stock_financial_hk_analysis_indicator_em 接口
        获取主要财务指标，包括 EPS、BPS、ROE、ROA 等

        Args:
            symbol: 港股代码

        Returns:
            Dict: 财务指标数据
        """
        try:
            ak = importlib.import_module("akshare")

            # 标准化代码
            normalized_symbol = self._normalize_hk_symbol(symbol)

            # 检查缓存
            cache_key = f"financial_{normalized_symbol}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"📊 [港股财务指标] 使用缓存: {normalized_symbol}")
                return self.cache[cache_key]["data"]

            # 速率限制
            self._rate_limit()

            logger.info(f"📊 [港股财务指标] 获取财务指标: {normalized_symbol}")

            # 调用 AKShare 接口
            df = ak.stock_financial_hk_analysis_indicator_em(symbol=normalized_symbol)

            if df is None or df.empty:
                logger.warning(f"⚠️ [港股财务指标] 未获取到数据: {normalized_symbol}")
                return {}

            # 获取最新一期数据
            latest = df.iloc[0]

            # 提取关键指标
            indicators = {
                # 基本信息
                "report_date": str(latest.get("REPORT_DATE", "")),
                "fiscal_year": str(latest.get("FISCAL_YEAR", "")),
                # 每股指标
                "eps_basic": float(latest.get("BASIC_EPS", 0)) if pd.notna(latest.get("BASIC_EPS")) else None,
                "eps_diluted": float(latest.get("DILUTED_EPS", 0)) if pd.notna(latest.get("DILUTED_EPS")) else None,
                "eps_ttm": float(latest.get("EPS_TTM", 0)) if pd.notna(latest.get("EPS_TTM")) else None,
                "bps": float(latest.get("BPS", 0)) if pd.notna(latest.get("BPS")) else None,
                "per_netcash_operate": float(latest.get("PER_NETCASH_OPERATE", 0))
                if pd.notna(latest.get("PER_NETCASH_OPERATE"))
                else None,
                # 盈利能力指标
                "roe_avg": float(latest.get("ROE_AVG", 0)) if pd.notna(latest.get("ROE_AVG")) else None,
                "roe_yearly": float(latest.get("ROE_YEARLY", 0)) if pd.notna(latest.get("ROE_YEARLY")) else None,
                "roa": float(latest.get("ROA", 0)) if pd.notna(latest.get("ROA")) else None,
                "roic_yearly": float(latest.get("ROIC_YEARLY", 0)) if pd.notna(latest.get("ROIC_YEARLY")) else None,
                "net_profit_ratio": float(latest.get("NET_PROFIT_RATIO", 0))
                if pd.notna(latest.get("NET_PROFIT_RATIO"))
                else None,
                "gross_profit_ratio": float(latest.get("GROSS_PROFIT_RATIO", 0))
                if pd.notna(latest.get("GROSS_PROFIT_RATIO"))
                else None,
                # 营收指标
                "operate_income": float(latest.get("OPERATE_INCOME", 0))
                if pd.notna(latest.get("OPERATE_INCOME"))
                else None,
                "operate_income_yoy": float(latest.get("OPERATE_INCOME_YOY", 0))
                if pd.notna(latest.get("OPERATE_INCOME_YOY"))
                else None,
                "operate_income_qoq": float(latest.get("OPERATE_INCOME_QOQ", 0))
                if pd.notna(latest.get("OPERATE_INCOME_QOQ"))
                else None,
                "gross_profit": float(latest.get("GROSS_PROFIT", 0)) if pd.notna(latest.get("GROSS_PROFIT")) else None,
                "gross_profit_yoy": float(latest.get("GROSS_PROFIT_YOY", 0))
                if pd.notna(latest.get("GROSS_PROFIT_YOY"))
                else None,
                "holder_profit": float(latest.get("HOLDER_PROFIT", 0))
                if pd.notna(latest.get("HOLDER_PROFIT"))
                else None,
                "holder_profit_yoy": float(latest.get("HOLDER_PROFIT_YOY", 0))
                if pd.notna(latest.get("HOLDER_PROFIT_YOY"))
                else None,
                # 偿债能力指标
                "debt_asset_ratio": float(latest.get("DEBT_ASSET_RATIO", 0))
                if pd.notna(latest.get("DEBT_ASSET_RATIO"))
                else None,
                "current_ratio": float(latest.get("CURRENT_RATIO", 0))
                if pd.notna(latest.get("CURRENT_RATIO"))
                else None,
                # 现金流指标
                "ocf_sales": float(latest.get("OCF_SALES", 0)) if pd.notna(latest.get("OCF_SALES")) else None,
                # 数据源
                "source": "akshare_eastmoney",
                "data_count": len(df),
            }

            # 缓存数据
            self.cache[cache_key] = {"data": indicators, "timestamp": time.time()}
            self._save_cache()

            logger.info(f"✅ [港股财务指标] 成功获取: {normalized_symbol}, 报告期: {indicators['report_date']}")
            return indicators

        except Exception as e:
            logger.error(f"❌ [港股财务指标] 获取失败: {symbol} - {e}")
            return {}

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取港股基本信息

        Args:
            symbol: 港股代码

        Returns:
            Dict: 港股信息
        """
        try:
            company_name = self.get_company_name(symbol)

            return {
                "symbol": symbol,
                "name": company_name,
                "currency": "HKD",
                "exchange": "HKG",
                "market": "港股",
                "source": "improved_hk_provider",
            }

        except Exception as e:
            logger.error(f"❌ [港股] 获取股票信息失败: {e}")
            clean_symbol = self._normalize_hk_symbol(symbol)
            return {
                "symbol": symbol,
                "name": f"港股{clean_symbol}",
                "currency": "HKD",
                "exchange": "HKG",
                "market": "港股",
                "source": "error",
                "error": str(e),
            }
