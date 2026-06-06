# ruff: noqa: F401,F403,F405,F821
class _AKShareProviderMixin1:
    def __init__(self):
        super().__init__("AKShare")
        self.ak: Any = None
        self.connected = False
        self._stock_list_cache = None  # 缓存股票列表，避免重复获取
        self._cache_time = None  # 缓存时间
        self._initialize_akshare()

    def _initialize_akshare(self):
        """初始化AKShare连接"""
        try:
            ak = importlib.import_module("akshare")
            requests = cast(Any, importlib.import_module("requests"))
            time = importlib.import_module("time")

            # 尝试导入 curl_cffi，如果可用则使用它来绕过反爬虫
            try:
                curl_requests = getattr(
                    importlib.import_module("curl_cffi"), "requests"
                )
                use_curl_cffi = True
                logger.info("🔧 检测到 curl_cffi，将使用它来模拟真实浏览器 TLS 指纹")
            except ImportError:
                use_curl_cffi = False
                logger.warning(
                    "⚠️ curl_cffi 未安装，将使用标准 requests（可能被反爬虫拦截）"
                )
                logger.warning("   建议安装: pip install curl-cffi")

            # 修复AKShare的bug：设置requests的默认headers，并添加请求延迟
            # AKShare的stock_news_em()函数没有设置必要的headers，导致API返回空响应
            if not hasattr(requests, "_akshare_headers_patched"):
                last_request_time: Dict[str, float] = {
                    "time": 0.0
                }  # 使用字典以便在闭包中修改

                def patched_get(url, **kwargs):
                    """
                    包装requests.get方法，自动添加必要的headers和请求延迟
                    修复AKShare stock_news_em()函数缺少headers的问题
                    如果可用，使用 curl_cffi 模拟真实浏览器 TLS 指纹
                    """
                    is_eastmoney_request = "eastmoney.com" in url
                    # 添加请求延迟，避免被反爬虫封禁
                    # 只对东方财富网的请求添加延迟
                    if is_eastmoney_request:
                        current_time = time.time()
                        time_since_last_request = (
                            current_time - last_request_time["time"]
                        )
                        if time_since_last_request < 0.5:  # 至少间隔0.5秒
                            time.sleep(0.5 - time_since_last_request)
                        last_request_time["time"] = time.time()

                    # 如果是东方财富网的请求，且 curl_cffi 可用，使用它来绕过反爬虫
                    if use_curl_cffi and is_eastmoney_request:
                        try:
                            # 使用 curl_cffi 模拟 Chrome 120 的 TLS 指纹
                            # 注意：使用 impersonate 时，不要传递自定义 headers，让 curl_cffi 自动设置
                            curl_kwargs = {
                                "timeout": kwargs.get("timeout", 10),
                                "impersonate": "chrome120",  # 模拟 Chrome 120
                                "proxies": {},
                            }

                            # 只传递非 headers 的参数
                            if "params" in kwargs:
                                curl_kwargs["params"] = kwargs["params"]
                            # 不传递 headers，让 impersonate 自动设置
                            if "data" in kwargs:
                                curl_kwargs["data"] = kwargs["data"]
                            if "json" in kwargs:
                                curl_kwargs["json"] = kwargs["json"]

                            response = curl_requests.get(url, **curl_kwargs)
                            # curl_cffi 的响应对象已经兼容 requests.Response
                            return response
                        except Exception as e:
                            # curl_cffi 失败，回退到标准 requests
                            error_msg = str(e)
                            # 忽略 TLS 库错误和 400 错误的详细日志（这是 Docker 环境的已知问题）
                            if (
                                "invalid library" not in error_msg
                                and "400" not in error_msg
                            ):
                                logger.warning(
                                    f"⚠️ curl_cffi 请求失败，回退到标准 requests: {e}"
                                )

                    # 标准 requests 请求（非东方财富网，或 curl_cffi 不可用/失败）
                    # 本地 A 股数据请求不要继承终端/系统代理，避免 7897 等代理影响国内数据源。
                    kwargs["proxies"] = {}
                    # 设置浏览器请求头
                    if "headers" not in kwargs or kwargs["headers"] is None:
                        kwargs["headers"] = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Accept-Encoding": "gzip, deflate, br",
                            "Referer": "https://www.eastmoney.com/",
                            "Connection": "keep-alive",
                        }
                    elif isinstance(kwargs["headers"], dict):
                        # 如果已有headers，确保包含必要的字段
                        if "User-Agent" not in kwargs["headers"]:
                            kwargs["headers"]["User-Agent"] = (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            )
                        if "Referer" not in kwargs["headers"]:
                            kwargs["headers"]["Referer"] = "https://www.eastmoney.com/"
                        if "Accept" not in kwargs["headers"]:
                            kwargs["headers"]["Accept"] = (
                                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                            )
                        if "Accept-Language" not in kwargs["headers"]:
                            kwargs["headers"]["Accept-Language"] = (
                                "zh-CN,zh;q=0.9,en;q=0.8"
                            )

                    # 添加重试机制（最多3次）
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            with requests.Session() as session:
                                session.trust_env = False
                                return session.get(url, **kwargs)
                        except Exception as e:
                            # 检查是否是SSL错误
                            error_str = str(e)
                            is_ssl_error = (
                                "SSL" in error_str
                                or "ssl" in error_str
                                or "UNEXPECTED_EOF_WHILE_READING" in error_str
                            )

                            if is_ssl_error and attempt < max_retries - 1:
                                # SSL错误，等待后重试
                                wait_time = 0.5 * (attempt + 1)  # 递增等待时间
                                time.sleep(wait_time)
                                continue
                            else:
                                # 非SSL错误或已达到最大重试次数，直接抛出
                                raise

                # 应用patch
                requests.get = patched_get
                setattr(requests, "_akshare_headers_patched", True)

                if use_curl_cffi:
                    logger.info(
                        "🔧 已修复AKShare的headers问题，使用 curl_cffi 模拟真实浏览器（Chrome 120）"
                    )
                else:
                    logger.info(
                        "🔧 已修复AKShare的headers问题，并添加请求延迟（0.5秒）"
                    )

            self.ak = ak
            self.connected = True

            # 配置超时和重试
            self._configure_timeout()

            logger.info("✅ AKShare连接成功")
        except ImportError as e:
            logger.error(f"❌ AKShare未安装: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"❌ AKShare初始化失败: {e}")
            self.connected = False

    def _get_stock_news_direct(
        self, symbol: str, limit: int = 10
    ) -> Optional[pd.DataFrame]:
        """
        直接调用东方财富网新闻 API（绕过 AKShare）
        使用 curl_cffi 模拟真实浏览器，适用于 Docker 环境

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            新闻 DataFrame 或 None
        """
        try:
            curl_requests = getattr(importlib.import_module("curl_cffi"), "requests")
            json = importlib.import_module("json")
            time = importlib.import_module("time")
            importlib.import_module("os")

            # 标准化股票代码
            symbol_6 = symbol.zfill(6)

            # 构建请求参数
            url = "https://search-api-web.eastmoney.com/search/jsonp"
            param = {
                "uid": "",
                "keyword": symbol_6,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {
                    "cmsArticleWebOld": {
                        "searchScope": "default",
                        "sort": "default",
                        "pageIndex": 1,
                        "pageSize": limit,
                        "preTag": "<em>",
                        "postTag": "</em>",
                    }
                },
            }

            params = {
                "cb": f"jQuery{int(time.time() * 1000)}",
                "param": json.dumps(param),
                "_": str(int(time.time() * 1000)),
            }

            # 使用 curl_cffi 发送请求
            response = curl_requests.get(
                url,
                params=params,
                timeout=10,
                impersonate="chrome120",
                proxies={},
            )

            if response.status_code != 200:
                self.logger.error(
                    f"❌ {symbol} 东方财富网 API 返回错误: {response.status_code}"
                )
                return None

            # 解析 JSONP 响应
            text = response.text
            if text.startswith("jQuery"):
                text = text[text.find("(") + 1 : text.rfind(")")]

            data = json.loads(text)

            # 检查返回数据
            if "result" not in data or "cmsArticleWebOld" not in data["result"]:
                self.logger.error(f"❌ {symbol} 东方财富网 API 返回数据结构异常")
                return None

            articles = data["result"]["cmsArticleWebOld"]

            if not articles:
                self.logger.warning(f"⚠️ {symbol} 未获取到新闻")
                return None

            # 转换为 DataFrame（与 AKShare 格式兼容）
            news_data = []
            for article in articles:
                news_data.append(
                    {
                        "新闻标题": article.get("title", ""),
                        "新闻内容": article.get("content", ""),
                        "发布时间": article.get("date", ""),
                        "新闻链接": article.get("url", ""),
                        "关键词": article.get("keywords", ""),
                        "新闻来源": article.get("source", "东方财富网"),
                        "新闻类型": article.get("type", ""),
                    }
                )

            df = pd.DataFrame(news_data)
            self.logger.info(f"✅ {symbol} 直接调用 API 获取新闻成功: {len(df)} 条")
            return df

        except Exception as e:
            self.logger.error(f"❌ {symbol} 直接调用 API 失败: {e}")
            return None

    def _configure_timeout(self):
        """配置AKShare的超时设置"""
        try:
            socket = importlib.import_module("socket")
            socket.setdefaulttimeout(60)  # 60秒超时
            logger.info("🔧 AKShare超时配置完成: 60秒")
        except Exception as e:
            logger.warning(f"⚠️ AKShare超时配置失败: {e}")

    async def connect(self) -> bool:
        """连接到AKShare数据源"""
        return await self.test_connection()

    async def test_connection(self) -> bool:
        """测试AKShare连接"""
        if not self.connected:
            return False

        # AKShare 是基于网络爬虫的库，不需要传统的"连接"测试
        # 只要库已经导入成功，就认为可用
        # 实际的网络请求会在具体调用时进行，并有各自的错误处理
        logger.info("✅ AKShare连接测试成功（库已加载）")
        return True

    def get_stock_list_sync(self) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本）"""
        if not self.connected:
            return None

        try:
            logger.info("📋 获取AKShare股票列表（同步）...")
            stock_df = self.ak.stock_info_a_code_name()

            if stock_df is None or stock_df.empty:
                logger.warning("⚠️ AKShare股票列表为空")
                return None

            logger.info(f"✅ AKShare股票列表获取成功: {len(stock_df)}只股票")
            return stock_df

        except Exception as e:
            logger.error(f"❌ AKShare获取股票列表失败: {e}")
            return None

    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表

        Returns:
            股票列表，包含代码和名称
        """
        if not self.connected:
            return []

        try:
            logger.info("📋 获取AKShare股票列表...")

            # 使用线程池异步获取股票列表，添加超时保护
            def fetch_stock_list():
                return self.ak.stock_info_a_code_name()

            stock_df = await asyncio.to_thread(fetch_stock_list)

            if stock_df is None or stock_df.empty:
                logger.warning("⚠️ AKShare股票列表为空")
                return []

            # 转换为标准格式
            stock_list = []
            for _, row in stock_df.iterrows():
                stock_list.append(
                    {
                        "code": str(row.get("code", "")),
                        "name": str(row.get("name", "")),
                        "source": "akshare",
                    }
                )

            logger.info(f"✅ AKShare股票列表获取成功: {len(stock_list)}只股票")
            return stock_list

        except Exception as e:
            logger.error(f"❌ AKShare获取股票列表失败: {e}")
            return []

    async def get_stock_basic_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基础信息

        Args:
            code: 股票代码

        Returns:
            标准化的股票基础信息
        """
        if not self.connected:
            return None

        try:
            logger.debug(f"📊 获取{code}基础信息...")

            # 获取股票基本信息
            stock_info = await self._get_stock_info_detail(code)

            if not stock_info:
                logger.warning(f"⚠️ 未找到{code}的基础信息")
                return None

            # 转换为标准化字典
            basic_info = {
                "code": code,
                "name": stock_info.get("name", f"股票{code}"),
                "area": stock_info.get("area", "未知"),
                "industry": stock_info.get("industry", "未知"),
                "market": self._determine_market(code),
                "list_date": stock_info.get("list_date", ""),
                # 扩展字段
                "full_symbol": self._get_full_symbol(code),
                "market_info": self._get_market_info(code),
                "data_source": "akshare",
                "last_sync": datetime.now(timezone.utc),
                "sync_status": "success",
            }

            logger.debug(f"✅ {code}基础信息获取成功")
            return basic_info

        except Exception as e:
            logger.error(f"❌ 获取{code}基础信息失败: {e}")
            return None

    async def _get_stock_list_cached(self):
        """获取缓存的股票列表（避免重复获取）"""
        datetime = getattr(importlib.import_module("datetime"), "datetime")
        timedelta = getattr(importlib.import_module("datetime"), "timedelta")

        # 如果缓存存在且未过期（1小时），直接返回
        if self._stock_list_cache is not None and self._cache_time is not None:
            if datetime.now() - self._cache_time < timedelta(hours=1):
                return self._stock_list_cache

        # 否则重新获取
        def fetch_stock_list():
            return self.ak.stock_info_a_code_name()

        try:
            stock_list = await asyncio.to_thread(fetch_stock_list)
            if stock_list is not None and not stock_list.empty:
                self._stock_list_cache = stock_list
                self._cache_time = datetime.now()
                logger.info(f"✅ 股票列表缓存更新: {len(stock_list)} 只股票")
                return stock_list
        except Exception as e:
            logger.error(f"❌ 获取股票列表失败: {e}")

        return None

    async def _get_stock_info_detail(self, code: str) -> Dict[str, Any]:
        """获取股票详细信息"""
        try:
            # 方法1: 尝试获取个股详细信息（包含行业、地区等详细信息）
            def fetch_individual_info():
                return self.ak.stock_individual_info_em(symbol=code)

            try:
                stock_info = await asyncio.to_thread(fetch_individual_info)

                if stock_info is not None and not stock_info.empty:
                    # 解析信息
                    info = {"code": code}

                    # 提取股票名称
                    name_row = stock_info[stock_info["item"] == "股票简称"]
                    if not name_row.empty:
                        info["name"] = str(name_row["value"].iloc[0])

                    # 提取行业信息
                    industry_row = stock_info[stock_info["item"] == "所属行业"]
                    if not industry_row.empty:
                        info["industry"] = str(industry_row["value"].iloc[0])

                    # 提取地区信息
                    area_row = stock_info[stock_info["item"] == "所属地区"]
                    if not area_row.empty:
                        info["area"] = str(area_row["value"].iloc[0])

                    # 提取上市日期
                    list_date_row = stock_info[stock_info["item"] == "上市时间"]
                    if not list_date_row.empty:
                        info["list_date"] = str(list_date_row["value"].iloc[0])

                    return info
            except Exception as e:
                logger.debug(f"获取{code}个股详细信息失败: {e}")

            # 方法2: 从缓存的股票列表中获取基本信息（只有代码和名称）
            try:
                stock_list = await self._get_stock_list_cached()
                if stock_list is not None and not stock_list.empty:
                    stock_row = stock_list[stock_list["code"] == code]
                    if not stock_row.empty:
                        return {
                            "code": code,
                            "name": str(stock_row["name"].iloc[0]),
                            "industry": "未知",
                            "area": "未知",
                        }
            except Exception as e:
                logger.debug(f"从股票列表获取{code}信息失败: {e}")

            # 如果都失败，返回基本信息
            return {
                "code": code,
                "name": f"股票{code}",
                "industry": "未知",
                "area": "未知",
            }

        except Exception as e:
            logger.debug(f"获取{code}详细信息失败: {e}")
            return {
                "code": code,
                "name": f"股票{code}",
                "industry": "未知",
                "area": "未知",
            }

    def _determine_market(self, code: str) -> str:
        """根据股票代码判断市场"""
        if code.startswith(("60", "68")):
            return "上海证券交易所"
        elif code.startswith(("00", "30")):
            return "深圳证券交易所"
        elif code.startswith("8"):
            return "北京证券交易所"
        else:
            return "未知市场"

    def _get_full_symbol(self, code: str) -> str:
        """
        获取完整股票代码

        Args:
            code: 6位股票代码

        Returns:
            完整标准化代码，如果无法识别则返回原始代码（确保不为空）
        """
        # 确保 code 不为空
        if not code:
            return ""

        # 标准化为字符串
        code = str(code).strip()

        # 根据代码前缀判断交易所
        if code.startswith(("60", "68", "90")):  # 上海证券交易所（增加90开头的B股）
            return f"{code}.SS"
        elif code.startswith(("00", "30", "20")):  # 深圳证券交易所（增加20开头的B股）
            return f"{code}.SZ"
        elif code.startswith(("8", "4")):  # 北京证券交易所（增加4开头的新三板）
            return f"{code}.BJ"
        else:
            # 无法识别的代码，返回原始代码（确保不为空）
            return code if code else ""

    def _get_market_info(self, code: str) -> Dict[str, Any]:
        """获取市场信息"""
        if code.startswith(("60", "68")):
            return {
                "market_type": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        elif code.startswith(("00", "30")):
            return {
                "market_type": "CN",
                "exchange": "SZSE",
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        elif code.startswith("8"):
            return {
                "market_type": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
        else:
            return {
                "market_type": "CN",
                "exchange": "UNKNOWN",
                "exchange_name": "未知交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai",
            }
